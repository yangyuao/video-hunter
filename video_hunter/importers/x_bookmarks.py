from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from video_hunter import db
from video_hunter.connectors.base import CandidateVideo, utc_now_iso
from video_hunter.dedup import rebuild_duplicate_groups
from video_hunter.clustering import rebuild_topic_clusters


@dataclass(frozen=True)
class XBookmarkImportResult:
    received: int
    video_posts: int
    inserted: int
    skipped: int
    duplicate_groups: int
    topic_clusters: int


def import_x_bookmarks(items: list[dict[str, Any]]) -> XBookmarkImportResult:
    db.init_db()
    inserted = 0
    skipped = 0
    video_posts = 0
    fetched_at = utc_now_iso()

    for item in items:
        if not item.get("has_video"):
            skipped += 1
            continue

        tweet_url = item.get("tweet_url") or item.get("source_url")
        tweet_id = item.get("tweet_id")
        if not tweet_url or not tweet_id:
            skipped += 1
            continue

        video_posts += 1
        media_url = item.get("media_url")
        if isinstance(media_url, str) and media_url.startswith("blob:"):
            media_url = None

        candidate = CandidateVideo(
            platform="x",
            source_url=tweet_url,
            media_url=media_url,
            platform_item_id=f"bookmark:{tweet_id}",
            author_name=item.get("author_name") or item.get("author_handle"),
            title=_title_from_item(item),
            description=item.get("text"),
            text=item.get("text"),
            published_at=item.get("published_at"),
            thumbnail_url=item.get("thumbnail_url"),
            evidence_type="chrome_x_bookmarks",
            confidence_score=0.75,
            raw_metadata={
                "tweet_id": tweet_id,
                "author_handle": item.get("author_handle"),
                "has_video": item.get("has_video"),
                "video_count": item.get("video_count"),
                "thumbnail_url": item.get("thumbnail_url"),
                "exported_at": item.get("exported_at"),
                "fetched_at": fetched_at,
            },
        )
        video_id, _occurrence_id, created = db.upsert_candidate(
            candidate,
            target_type="bookmark",
            fetched_at=fetched_at,
        )
        if created:
            inserted += 1
            db.update_video_storage(video_id, media_url, "remote_stream" if media_url else "metadata_only")
        else:
            skipped += 1

    groups = rebuild_duplicate_groups()
    clusters = rebuild_topic_clusters()
    return XBookmarkImportResult(
        received=len(items),
        video_posts=video_posts,
        inserted=inserted,
        skipped=skipped,
        duplicate_groups=len(groups),
        topic_clusters=len(clusters),
    )


def _title_from_item(item: dict[str, Any]) -> str | None:
    text = item.get("text")
    if not isinstance(text, str):
        return None
    compact = " ".join(text.split())
    return compact[:120] if compact else None
