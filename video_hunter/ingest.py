from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

from video_hunter import db
from video_hunter.analyzer import analyze_video
from video_hunter.clustering import rebuild_topic_clusters
from video_hunter.config import outbound_proxy_url, settings
from video_hunter.connectors import CrawlContext, SourceTarget, get_connector
from video_hunter.dedup import rebuild_duplicate_groups


DIRECT_DOWNLOAD_EXTENSIONS = {".mp4", ".m4v", ".mov", ".webm"}


@dataclass(frozen=True)
class IngestResult:
    source_id: int
    discovered: int
    inserted: int
    downloaded: int
    analyzed: int
    duplicate_groups: int
    topic_clusters: int
    errors: list[str]


def crawl_source(source_id: int, limit: int = 50) -> IngestResult:
    db.init_db()
    source_row = db.get_source(source_id)
    if not source_row:
        raise ValueError(f"Source not found: {source_id}")

    source = SourceTarget(
        id=int(source_row["id"]),
        platform=source_row["platform"],
        target_type=source_row["target_type"],
        target_value=source_row["target_value"],
        crawl_interval_seconds=int(source_row["crawl_interval_seconds"]),
        enabled=bool(source_row["enabled"]),
    )
    if not source.enabled:
        raise ValueError(f"Source is disabled: {source_id}")

    context = CrawlContext(limit=limit)
    errors: list[str] = []
    discovered = inserted = downloaded = analyzed = 0

    try:
        connector = get_connector(source.platform)
        candidates = connector.crawl(source, context)
        discovered = len(candidates)
        for candidate in candidates:
            video_id, _occurrence_id, created = db.upsert_candidate(
                candidate,
                target_type=source.target_type,
                fetched_at=context.fetched_at,
            )
            if not created:
                continue
            inserted += 1
            if not candidate.media_url:
                db.update_video_storage(video_id, None, "metadata_only")
                continue

            if settings.download_media and _is_direct_download(candidate.media_url):
                try:
                    storage_path = download_media(video_id, candidate.media_url)
                    downloaded += 1
                    db.update_video_storage(video_id, str(storage_path), "downloaded")
                    try:
                        analysis = analyze_video(storage_path)
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
                        errors.append(f"analysis failed for video {video_id}: {exc}")
                        db.update_video_storage(video_id, str(storage_path), "analysis_failed")
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"download failed for video {video_id}: {exc}")
                    db.update_video_storage(video_id, None, "download_failed")
            else:
                db.update_video_storage(video_id, None, "remote_stream")

        groups = rebuild_duplicate_groups()
        clusters = rebuild_topic_clusters()
        db.mark_source_result(source_id, error="\n".join(errors) if errors else None)
        return IngestResult(
            source_id=source_id,
            discovered=discovered,
            inserted=inserted,
            downloaded=downloaded,
            analyzed=analyzed,
            duplicate_groups=len(groups),
            topic_clusters=len(clusters),
            errors=errors,
        )
    except Exception as exc:  # noqa: BLE001
        db.mark_source_result(source_id, error=str(exc))
        raise


def crawl_all(limit: int = 50) -> list[IngestResult]:
    results = []
    for source in db.list_sources(enabled_only=True):
        source_id = int(source["id"])
        try:
            results.append(crawl_source(source_id, limit=limit))
        except Exception as exc:  # noqa: BLE001
            results.append(
                IngestResult(
                    source_id=source_id,
                    discovered=0,
                    inserted=0,
                    downloaded=0,
                    analyzed=0,
                    duplicate_groups=0,
                    topic_clusters=0,
                    errors=[str(exc)],
                )
            )
    return results


def rebuild_indexes() -> dict[str, int]:
    db.init_db()
    groups = rebuild_duplicate_groups()
    clusters = rebuild_topic_clusters()
    return {"duplicate_groups": len(groups), "topic_clusters": len(clusters)}


def download_media(video_id: int, media_url: str) -> Path:
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    destination_dir = settings.storage_dir / "videos" / str(video_id // 1000)
    destination_dir.mkdir(parents=True, exist_ok=True)
    extension = _extension_from_url(media_url) or ".bin"
    destination = destination_dir / f"{video_id}{extension}"
    temp_destination = destination.with_suffix(destination.suffix + ".part")
    max_bytes = settings.max_download_mb * 1024 * 1024

    with httpx.Client(follow_redirects=True, timeout=60, proxy=outbound_proxy_url()) as client:
        with client.stream("GET", media_url, headers={"User-Agent": "VideoHunter/0.1"}) as response:
            response.raise_for_status()
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > max_bytes:
                raise RuntimeError(
                    f"file is larger than VIDEO_HUNTER_MAX_DOWNLOAD_MB={settings.max_download_mb}"
                )
            written = 0
            with temp_destination.open("wb") as file:
                for chunk in response.iter_bytes(1024 * 1024):
                    if not chunk:
                        continue
                    written += len(chunk)
                    if written > max_bytes:
                        raise RuntimeError(
                            f"download exceeded VIDEO_HUNTER_MAX_DOWNLOAD_MB={settings.max_download_mb}"
                        )
                    file.write(chunk)

    shutil.move(str(temp_destination), destination)
    return destination


def _is_direct_download(media_url: str) -> bool:
    return _extension_from_url(media_url) in DIRECT_DOWNLOAD_EXTENSIONS


def _extension_from_url(media_url: str) -> str | None:
    path = urlparse(media_url).path.lower()
    for extension in DIRECT_DOWNLOAD_EXTENSIONS:
        if path.endswith(extension):
            return extension
    return None
