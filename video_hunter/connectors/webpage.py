from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from video_hunter.config import outbound_proxy_url
from video_hunter.connectors.base import CandidateVideo, Connector, CrawlContext, SourceTarget


VIDEO_EXTENSIONS = (".mp4", ".m4v", ".mov", ".webm", ".m3u8")


class WebPageConnector(Connector):
    def crawl(self, source: SourceTarget, context: CrawlContext) -> list[CandidateVideo]:
        proxy_url = outbound_proxy_url()
        with httpx.Client(follow_redirects=True, timeout=30, proxy=proxy_url) as client:
            response = client.get(
                source.target_value,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; VideoHunter/0.1; "
                        "+https://example.local/video-hunter)"
                    )
                },
            )
            response.raise_for_status()

        return extract_video_candidates(
            page_url=str(response.url),
            html=response.text,
            platform=source.platform,
            fetched_at=context.fetched_at,
            limit=context.limit,
        )


def extract_video_candidates(
    page_url: str,
    html: str,
    platform: str = "webpage",
    fetched_at: str | None = None,
    limit: int = 50,
) -> list[CandidateVideo]:
    soup = BeautifulSoup(html, "html.parser")
    page_title = _text_or_none(soup.title.string if soup.title else None)
    meta = _collect_meta(soup)
    published_at = (
        meta.get("article:published_time")
        or meta.get("video:release_date")
        or meta.get("datePublished")
    )
    title = meta.get("og:title") or meta.get("twitter:title") or page_title
    description = meta.get("og:description") or meta.get("description")

    candidates: list[CandidateVideo] = []
    seen: set[str] = set()

    for data in _json_ld_objects(soup):
        for video in _walk_video_objects(data):
            media_url = _first_string(
                video.get("contentUrl"),
                video.get("embedUrl"),
                video.get("url"),
            )
            if not media_url:
                continue
            absolute_media_url = urljoin(page_url, media_url)
            if absolute_media_url in seen:
                continue
            seen.add(absolute_media_url)
            candidates.append(
                CandidateVideo(
                    platform=platform,
                    source_url=page_url,
                    media_url=absolute_media_url,
                    platform_item_id=absolute_media_url,
                    title=_first_string(video.get("name"), title),
                    description=_first_string(video.get("description"), description),
                    published_at=_first_string(video.get("uploadDate"), published_at),
                    thumbnail_url=_first_thumbnail(video.get("thumbnailUrl")),
                    evidence_type="json_ld",
                    confidence_score=0.85,
                    raw_metadata={"json_ld": video, "fetched_at": fetched_at},
                )
            )

    for key in ("og:video", "og:video:url", "og:video:secure_url", "twitter:player:stream"):
        media_url = meta.get(key)
        if media_url:
            _append_candidate(
                candidates,
                seen,
                CandidateVideo(
                    platform=platform,
                    source_url=page_url,
                    media_url=urljoin(page_url, media_url),
                    platform_item_id=urljoin(page_url, media_url),
                    title=title,
                    description=description,
                    published_at=published_at,
                    thumbnail_url=meta.get("og:image") or meta.get("twitter:image"),
                    evidence_type=f"meta:{key}",
                    confidence_score=0.8,
                    raw_metadata={"meta": meta, "fetched_at": fetched_at},
                ),
            )

    for tag in soup.select("video[src], video source[src], source[src]"):
        src = tag.get("src")
        if not src:
            continue
        media_url = urljoin(page_url, src)
        _append_candidate(
            candidates,
            seen,
            CandidateVideo(
                platform=platform,
                source_url=page_url,
                media_url=media_url,
                platform_item_id=media_url,
                title=title,
                description=description,
                published_at=published_at,
                thumbnail_url=meta.get("og:image") or meta.get("twitter:image"),
                evidence_type="html_video_tag",
                confidence_score=0.75,
                raw_metadata={"tag": str(tag)[:1000], "fetched_at": fetched_at},
            ),
        )

    for tag in soup.select("a[href]"):
        href = tag.get("href") or ""
        if _looks_like_video_url(href):
            media_url = urljoin(page_url, href)
            link_title = _text_or_none(tag.get_text(" ", strip=True)) or title
            _append_candidate(
                candidates,
                seen,
                CandidateVideo(
                    platform=platform,
                    source_url=media_url,
                    media_url=media_url,
                    platform_item_id=media_url,
                    title=link_title,
                    description=description,
                    published_at=published_at,
                    thumbnail_url=meta.get("og:image") or meta.get("twitter:image"),
                    evidence_type="html_link",
                    confidence_score=0.65,
                    raw_metadata={"page_url": page_url, "fetched_at": fetched_at},
                ),
            )

    if not candidates:
        embedded_urls = _extract_video_urls_from_text(html)
        for media_url in embedded_urls:
            absolute_media_url = urljoin(page_url, media_url)
            _append_candidate(
                candidates,
                seen,
                CandidateVideo(
                    platform=platform,
                    source_url=absolute_media_url,
                    media_url=absolute_media_url,
                    platform_item_id=absolute_media_url,
                    title=title,
                    description=description,
                    published_at=published_at,
                    thumbnail_url=meta.get("og:image") or meta.get("twitter:image"),
                    evidence_type="html_text_url",
                    confidence_score=0.55,
                    raw_metadata={"page_url": page_url, "fetched_at": fetched_at},
                ),
            )

    return candidates[:limit]


def _append_candidate(
    candidates: list[CandidateVideo],
    seen: set[str],
    candidate: CandidateVideo,
) -> None:
    identity = candidate.media_url or candidate.source_url
    if identity in seen:
        return
    seen.add(identity)
    candidates.append(candidate)


def _collect_meta(soup: BeautifulSoup) -> dict[str, str]:
    result: dict[str, str] = {}
    for tag in soup.find_all("meta"):
        key = tag.get("property") or tag.get("name") or tag.get("itemprop")
        value = tag.get("content")
        if key and value:
            result[key] = value.strip()
    return result


def _json_ld_objects(soup: BeautifulSoup) -> list[Any]:
    objects: list[Any] = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not tag.string:
            continue
        try:
            objects.append(json.loads(tag.string))
        except json.JSONDecodeError:
            continue
    return objects


def _walk_video_objects(data: Any) -> list[dict[str, Any]]:
    videos: list[dict[str, Any]] = []
    if isinstance(data, dict):
        node_type = data.get("@type")
        if node_type == "VideoObject" or (
            isinstance(node_type, list) and "VideoObject" in node_type
        ):
            videos.append(data)
        for key in ("@graph", "itemListElement", "mainEntity", "hasPart", "video"):
            if key in data:
                videos.extend(_walk_video_objects(data[key]))
    elif isinstance(data, list):
        for item in data:
            videos.extend(_walk_video_objects(item))
    return videos


def _looks_like_video_url(value: str) -> bool:
    lowered = value.lower().split("?", 1)[0]
    return lowered.endswith(VIDEO_EXTENSIONS)


def _extract_video_urls_from_text(text: str) -> list[str]:
    pattern = r"https?://[^\s\"'<>]+(?:\.mp4|\.m4v|\.mov|\.webm|\.m3u8)(?:\?[^\s\"'<>]+)?"
    return list(dict.fromkeys(re.findall(pattern, text, flags=re.IGNORECASE)))


def _first_string(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _first_thumbnail(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                return item
    return None


def _text_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
