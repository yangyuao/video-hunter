from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from video_hunter import db
from video_hunter.analyzer import analyze_video
from video_hunter.clustering import rebuild_topic_clusters
from video_hunter.config import outbound_proxy_url
from video_hunter.dedup import rebuild_duplicate_groups
from video_hunter.ingest import download_media


VX_API_BASE = "https://api.vxtwitter.com/Twitter/status"
TWEET_ID_PATTERN = re.compile(r"/status/(\d+)")
SAFETY_REVIEW_PATTERNS = (
    "未成年",
    "未滿",
    "未满",
    "未成年人",
    "小学生",
    "小學生",
    "初中生",
    "中学生",
    "中學生",
    "高中生",
    "高一",
    "高二",
    "高三",
    "高考完",
    "幼女",
    "萝莉",
    "蘿莉",
    "12岁",
    "12歲",
    "13岁",
    "13歲",
    "14岁",
    "14歲",
    "15岁",
    "15歲",
    "16岁",
    "16歲",
    "17岁",
    "17歲",
)


@dataclass(frozen=True)
class XMediaResolveResult:
    checked: int
    resolved: int
    downloaded: int
    analyzed: int
    failed: int
    duplicate_groups: int
    topic_clusters: int
    errors: list[str] = field(default_factory=list)


def resolve_and_download_x_videos(limit: int = 10, download: bool = True) -> XMediaResolveResult:
    db.init_db()
    rows = db.list_x_videos_needing_media(limit=limit)
    checked = resolved = downloaded = analyzed = failed = 0
    errors: list[str] = []

    for row in rows:
        checked += 1
        video_id = int(row["id"])
        source_url = row.get("source_url")
        if _requires_safety_review(row):
            failed += 1
            errors.append(f"video {video_id}: skipped by safety review keyword")
            db.update_video_storage(video_id, None, "safety_review")
            continue
        try:
            media_url = _existing_media_url(row)
            if media_url:
                payload = {"media_url": media_url}
            else:
                payload = resolve_x_media(source_url)
                media_url = payload.get("media_url")
                if not media_url:
                    failed += 1
                    errors.append(f"video {video_id}: no mp4 media in resolver response")
                    db.update_video_storage(video_id, None, "x_media_unresolved")
                    continue
                db.update_x_video_media_url(video_id, media_url, resolver_payload=payload)
                resolved += 1

            if not download:
                db.update_video_storage(video_id, None, "remote_stream")
                continue

            try:
                path = download_media(video_id, media_url)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                errors.append(f"video {video_id}: {exc}")
                if _is_oversize_download_error(exc):
                    db.update_video_storage(video_id, None, "remote_stream")
                elif _is_retryable_media_error(exc):
                    db.update_video_storage(video_id, None, "x_download_retryable")
                else:
                    db.update_video_storage(video_id, None, "download_failed")
                continue

            downloaded += 1
            db.update_video_storage(video_id, str(path), "downloaded")
            try:
                analysis = analyze_video(path)
                db.update_video_analysis(
                    video_id,
                    file_sha256=analysis.file_sha256,
                    duration_seconds=analysis.duration_seconds,
                    width=analysis.width,
                    height=analysis.height,
                    frame_hashes=analysis.frame_hashes,
                )
                analyzed += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"video {video_id}: analysis failed: {exc}")
                db.update_video_storage(video_id, str(path), "analysis_failed")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            errors.append(f"video {video_id}: {exc}")
            if not _is_retryable_media_error(exc):
                db.update_video_storage(video_id, None, "x_media_resolve_failed")

    groups = rebuild_duplicate_groups()
    clusters = rebuild_topic_clusters()
    return XMediaResolveResult(
        checked=checked,
        resolved=resolved,
        downloaded=downloaded,
        analyzed=analyzed,
        failed=failed,
        duplicate_groups=len(groups),
        topic_clusters=len(clusters),
        errors=errors,
    )


def resolve_x_media(source_url: str | None) -> dict[str, Any]:
    tweet_id = _tweet_id(source_url)
    if not tweet_id:
        raise ValueError(f"not an X status URL: {source_url}")
    url = f"{VX_API_BASE}/{tweet_id}"
    with httpx.Client(follow_redirects=True, timeout=30, proxy=outbound_proxy_url()) as client:
        response = client.get(url, headers={"User-Agent": "VideoHunter/0.1"})
        response.raise_for_status()
        payload = response.json()
    media = _select_media(payload)
    return {
        "tweet_id": tweet_id,
        "resolver": "api.vxtwitter.com",
        "resolver_url": url,
        "media_url": media.get("url") if media else None,
        "thumbnail_url": media.get("thumbnail_url") if media else None,
        "media_type": media.get("type") if media else None,
        "raw_media": media,
    }


def _is_retryable_media_error(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return isinstance(exc, httpx.TransportError)


def _is_oversize_download_error(exc: Exception) -> bool:
    message = str(exc)
    return isinstance(exc, RuntimeError) and (
        "VIDEO_HUNTER_MAX_DOWNLOAD_MB" in message or "download exceeded" in message
    )


def _existing_media_url(row: dict[str, Any]) -> str | None:
    media_url = row.get("media_url")
    if isinstance(media_url, str) and media_url and not media_url.startswith("blob:"):
        return media_url
    return None


def _requires_safety_review(row: dict[str, Any]) -> bool:
    haystack = "\n".join(
        str(row.get(key) or "")
        for key in ("title", "description", "raw_metadata_json", "source_url")
    )
    return any(pattern in haystack for pattern in SAFETY_REVIEW_PATTERNS)


def _tweet_id(source_url: str | None) -> str | None:
    if not source_url:
        return None
    match = TWEET_ID_PATTERN.search(source_url)
    return match.group(1) if match else None


def _select_media(payload: dict[str, Any]) -> dict[str, Any] | None:
    tweet = payload.get("tweet") if isinstance(payload.get("tweet"), dict) else payload
    media_items = tweet.get("media_extended") or tweet.get("mediaDetails") or []
    if not isinstance(media_items, list):
        return None
    videos = [
        item
        for item in media_items
        if isinstance(item, dict)
        and item.get("url")
        and (item.get("type") == "video" or str(item.get("url")).endswith(".mp4"))
    ]
    if not videos:
        return None
    return max(videos, key=lambda item: _resolution_score(item.get("url")))


def _resolution_score(url: Any) -> int:
    if not isinstance(url, str):
        return 0
    match = re.search(r"/(\d+)x(\d+)/", url)
    if not match:
        return 0
    return int(match.group(1)) * int(match.group(2))
