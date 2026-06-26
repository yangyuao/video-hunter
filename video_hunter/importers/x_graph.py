from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from video_hunter import db
from video_hunter.clustering import rebuild_topic_clusters
from video_hunter.connectors.base import CandidateVideo, utc_now_iso
from video_hunter.dedup import rebuild_duplicate_groups


DEFAULT_BOOKMARKS_PATH = Path("data/x_bookmarks_export.json")
DEFAULT_TIMELINES_PATH = Path("data/reports/x_author_recent_timelines.json")
DEFAULT_ORIGINALITY_PATH = Path("data/reports/x_author_recent_originality_report.json")


@dataclass(frozen=True)
class XGraphSyncResult:
    bookmark_authors: int
    report_authors: int
    timeline_authors: int
    repost_edges: int
    bookmark_edges: int
    timeline_video_posts: int
    imported_videos: int
    skipped_videos: int
    duplicate_groups: int
    topic_clusters: int


def sync_x_graph_from_files(
    bookmarks_path: Path = DEFAULT_BOOKMARKS_PATH,
    timelines_path: Path = DEFAULT_TIMELINES_PATH,
    originality_path: Path = DEFAULT_ORIGINALITY_PATH,
) -> XGraphSyncResult:
    db.init_db()
    bookmark_edges = _sync_bookmark_authors(bookmarks_path)
    report_authors = _sync_originality_report(originality_path)
    timeline_result = _sync_timelines(timelines_path)
    groups = rebuild_duplicate_groups()
    clusters = rebuild_topic_clusters()
    return XGraphSyncResult(
        bookmark_authors=bookmark_edges["authors"],
        report_authors=report_authors,
        timeline_authors=timeline_result["authors"],
        repost_edges=timeline_result["repost_edges"],
        bookmark_edges=bookmark_edges["edges"],
        timeline_video_posts=timeline_result["video_posts"],
        imported_videos=timeline_result["imported_videos"],
        skipped_videos=timeline_result["skipped_videos"],
        duplicate_groups=len(groups),
        topic_clusters=len(clusters),
    )


def _sync_bookmark_authors(path: Path) -> dict[str, int]:
    if not path.exists():
        return {"authors": 0, "edges": 0}
    payload = _load_json(path)
    items = payload.get("items", payload if isinstance(payload, list) else [])
    collection_handle = "my_x_bookmarks"
    db.upsert_x_account(
        handle=collection_handle,
        display_name="我的 X 书签",
        profile_url="https://x.com/i/bookmarks",
        account_kind="collection",
        raw_metadata={"source": str(path), "total_bookmarks": len(items)},
    )

    by_handle: dict[str, dict[str, Any]] = {}
    for item in items:
        handle = db.normalize_x_handle(item.get("author_handle"))
        if not handle:
            continue
        row = by_handle.setdefault(
            handle,
            {
                "display_names": Counter(),
                "bookmarked_posts": 0,
                "bookmarked_video_posts": 0,
                "urls": [],
            },
        )
        if item.get("author_name"):
            row["display_names"][str(item["author_name"])] += 1
        row["bookmarked_posts"] += 1
        if item.get("has_video"):
            row["bookmarked_video_posts"] += 1
        if item.get("tweet_url"):
            row["urls"].append(item["tweet_url"])

    edges = 0
    for handle, row in by_handle.items():
        display_name = _most_common(row["display_names"])
        db.upsert_x_account(
            handle=handle,
            display_name=display_name,
            bookmarked_posts=row["bookmarked_posts"],
            bookmarked_video_posts=row["bookmarked_video_posts"],
            raw_metadata={
                "source": str(path),
                "sample_bookmark_urls": row["urls"][:10],
            },
        )
        db.upsert_x_account_edge(
            source_handle=collection_handle,
            target_handle=handle,
            relationship_type="bookmarked_author",
            weight=row["bookmarked_posts"],
            evidence_url=f"x-bookmarks://{handle}",
            raw_metadata={"video_bookmarks": row["bookmarked_video_posts"]},
        )
        edges += 1
    return {"authors": len(by_handle), "edges": edges}


def _sync_originality_report(path: Path) -> int:
    if not path.exists():
        return 0
    payload = _load_json(path)
    count = 0
    for author in payload.get("authors", []):
        handle = db.normalize_x_handle(author.get("handle"))
        if not handle:
            continue
        label = _label_from_author_report(author)
        db.upsert_x_account(
            handle=handle,
            profile_url=author.get("profile_url") or db.x_profile_url(handle),
            bookmarked_posts=int(author.get("bookmarked_posts") or 0),
            bookmarked_video_posts=int(author.get("bookmarked_video_posts") or 0),
            timeline_posts=int(author.get("collected_posts") or 0),
            timeline_video_posts=int(author.get("video_posts") or 0),
            own_posts=int(author.get("own_posts") or 0),
            declared_reposts=int(author.get("declared_reposts") or 0),
            likely_non_original_posts=int(
                author.get("likely_non_original_own_posts")
                or author.get("likely_non_original_posts")
                or 0
            ),
            possible_non_original_posts=int(
                author.get("possible_non_original_own_posts")
                or author.get("possible_non_original_posts")
                or 0
            ),
            originality_label=label,
            raw_metadata={"source": str(path), "report_author": author},
        )
        count += 1
    return count


def _sync_timelines(path: Path) -> dict[str, int]:
    if not path.exists():
        return {"authors": 0, "repost_edges": 0, "video_posts": 0, "imported_videos": 0, "skipped_videos": 0}
    payload = _load_json(path)
    imported = 0
    skipped = 0
    video_posts = 0
    repost_edges = 0
    fetched_at = utc_now_iso()

    for author in payload.get("authors", []):
        handle = db.normalize_x_handle(author.get("handle"))
        if not handle:
            continue
        posts = author.get("posts") or []
        db.upsert_x_account(
            handle=handle,
            profile_url=author.get("url") or db.x_profile_url(handle),
            timeline_posts=int(author.get("collected_posts") or len(posts)),
            timeline_video_posts=sum(1 for post in posts if post.get("has_video")),
            own_posts=sum(1 for post in posts if not post.get("is_declared_repost")),
            declared_reposts=sum(1 for post in posts if post.get("is_declared_repost")),
            raw_metadata={
                "source": str(path),
                "timeline_error": author.get("error"),
                "max_posts_per_author": payload.get("max_posts_per_author"),
            },
        )

        for post in posts:
            article_handle = db.normalize_x_handle(post.get("article_handle"))
            target_handle = db.normalize_x_handle(post.get("target_handle") or handle)
            if post.get("is_declared_repost") and article_handle and target_handle:
                try:
                    db.upsert_x_account_edge(
                        source_handle=target_handle,
                        target_handle=article_handle,
                        relationship_type="reposted",
                        weight=1,
                        evidence_url=post.get("status_url"),
                        raw_metadata={
                            "status_id": post.get("status_id"),
                            "published_at": post.get("published_at"),
                            "has_video": bool(post.get("has_video")),
                        },
                    )
                    repost_edges += 1
                except ValueError:
                    pass

            if not post.get("has_video"):
                continue
            video_posts += 1
            candidate = _candidate_from_timeline_post(post, fallback_handle=target_handle or handle, fetched_at=fetched_at)
            if not candidate:
                skipped += 1
                continue
            video_id, _occurrence_id, created = db.upsert_candidate(
                candidate,
                target_type="profile_timeline",
                fetched_at=fetched_at,
            )
            if created:
                imported += 1
                db.update_video_storage(video_id, None, "metadata_only")
            else:
                skipped += 1

    return {
        "authors": len(payload.get("authors", [])),
        "repost_edges": repost_edges,
        "video_posts": video_posts,
        "imported_videos": imported,
        "skipped_videos": skipped,
    }


def _candidate_from_timeline_post(
    post: dict[str, Any],
    *,
    fallback_handle: str | None,
    fetched_at: str,
) -> CandidateVideo | None:
    status_url = post.get("status_url")
    status_id = post.get("status_id")
    if not status_url or not status_id:
        return None
    author_handle = db.normalize_x_handle(post.get("article_handle") or fallback_handle)
    if not author_handle:
        return None
    text = str(post.get("text") or "")
    return CandidateVideo(
        platform="x",
        source_url=status_url,
        media_url=None,
        platform_item_id=f"timeline:{status_id}",
        author_name=author_handle,
        title=_title_from_text(text, author_handle),
        description=text,
        text=text,
        published_at=post.get("published_at"),
        thumbnail_url=post.get("thumbnail_url"),
        evidence_type="chrome_x_author_timeline",
        confidence_score=0.7,
        raw_metadata={
            **post,
            "author_handle": author_handle,
            "fetched_at": fetched_at,
            "media_url_limit": "Chrome timeline export did not expose stable mp4 URL",
        },
    )


def _label_from_author_report(author: dict[str, Any]) -> str:
    likely = int(author.get("likely_non_original_own_posts") or author.get("likely_non_original_posts") or 0)
    possible = int(author.get("possible_non_original_own_posts") or author.get("possible_non_original_posts") or 0)
    own = int(author.get("own_posts") or 0)
    reposts = int(author.get("declared_reposts") or 0)
    videos = int(author.get("video_posts") or author.get("bookmarked_video_posts") or 0)
    if likely:
        return "likely_non_original"
    if possible:
        return "needs_review"
    if reposts and own == 0:
        return "reposter"
    if videos and own:
        return "likely_original"
    return "unknown"


def _title_from_text(text: str, handle: str) -> str:
    lines = [" ".join(line.split()) for line in text.splitlines()]
    lines = [line for line in lines if line and line != f"@{handle}" and line != handle]
    compact = " ".join(lines)
    return compact[:120] if compact else f"X video by @{handle}"


def _most_common(counter: Counter[str]) -> str | None:
    if not counter:
        return None
    return counter.most_common(1)[0][0]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
