from __future__ import annotations

import json
import sqlite3
from html import unescape
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from video_hunter.config import settings
from video_hunter.connectors.base import CandidateVideo


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@contextmanager
def connect(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    path = db_path or settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS source_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_value TEXT NOT NULL,
                crawl_interval_seconds INTEGER NOT NULL DEFAULT 3600,
                enabled INTEGER NOT NULL DEFAULT 1,
                last_crawled_at TEXT,
                last_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(platform, target_type, target_value)
            );

            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_group_id INTEGER,
                title TEXT,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'discovered',
                storage_path TEXT,
                file_sha256 TEXT,
                duration_seconds REAL,
                width INTEGER,
                height INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS video_occurrences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
                platform TEXT NOT NULL,
                target_type TEXT,
                source_url TEXT NOT NULL,
                media_url TEXT,
                platform_item_id TEXT NOT NULL,
                author_name TEXT,
                published_at TEXT,
                first_seen_at TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                raw_text TEXT,
                raw_metadata_json TEXT NOT NULL DEFAULT '{}',
                confidence_score REAL NOT NULL DEFAULT 0.5,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(platform, platform_item_id)
            );

            CREATE TABLE IF NOT EXISTS video_fingerprints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL UNIQUE REFERENCES videos(id) ON DELETE CASCADE,
                file_sha256 TEXT,
                frame_hashes_json TEXT NOT NULL DEFAULT '[]',
                audio_fingerprint TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS content_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                canonical_video_id INTEGER REFERENCES videos(id) ON DELETE SET NULL,
                earliest_occurrence_id INTEGER REFERENCES video_occurrences(id) ON DELETE SET NULL,
                duplicate_count INTEGER NOT NULL DEFAULT 1,
                confidence_score REAL NOT NULL DEFAULT 0.5,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS source_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                occurrence_id INTEGER NOT NULL REFERENCES video_occurrences(id) ON DELETE CASCADE,
                evidence_type TEXT NOT NULL,
                evidence_url TEXT,
                extracted_time TEXT,
                confidence_score REAL NOT NULL DEFAULT 0.5,
                raw_payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS topic_clusters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT NOT NULL,
                keywords_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS video_cluster_links (
                video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
                cluster_id INTEGER NOT NULL REFERENCES topic_clusters(id) ON DELETE CASCADE,
                score REAL NOT NULL DEFAULT 0.0,
                PRIMARY KEY(video_id, cluster_id)
            );

            CREATE TABLE IF NOT EXISTS x_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                handle TEXT NOT NULL UNIQUE,
                display_name TEXT,
                profile_url TEXT,
                avatar_url TEXT,
                account_kind TEXT NOT NULL DEFAULT 'person',
                bookmarked_posts INTEGER NOT NULL DEFAULT 0,
                bookmarked_video_posts INTEGER NOT NULL DEFAULT 0,
                timeline_posts INTEGER NOT NULL DEFAULT 0,
                timeline_video_posts INTEGER NOT NULL DEFAULT 0,
                own_posts INTEGER NOT NULL DEFAULT 0,
                declared_reposts INTEGER NOT NULL DEFAULT 0,
                likely_non_original_posts INTEGER NOT NULL DEFAULT 0,
                possible_non_original_posts INTEGER NOT NULL DEFAULT 0,
                originality_label TEXT NOT NULL DEFAULT 'unknown',
                manual_label TEXT,
                notes TEXT,
                raw_metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS x_account_edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_account_id INTEGER NOT NULL REFERENCES x_accounts(id) ON DELETE CASCADE,
                target_account_id INTEGER NOT NULL REFERENCES x_accounts(id) ON DELETE CASCADE,
                relationship_type TEXT NOT NULL,
                weight INTEGER NOT NULL DEFAULT 1,
                evidence_url TEXT,
                raw_metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(source_account_id, target_account_id, relationship_type, evidence_url)
            );

            CREATE TABLE IF NOT EXISTS video_manual_labels (
                video_id INTEGER PRIMARY KEY REFERENCES videos(id) ON DELETE CASCADE,
                origin_label TEXT NOT NULL DEFAULT 'unknown',
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_occurrences_video ON video_occurrences(video_id);
            CREATE INDEX IF NOT EXISTS idx_occurrences_source ON video_occurrences(platform, platform_item_id);
            CREATE INDEX IF NOT EXISTS idx_videos_sha ON videos(file_sha256);
            CREATE INDEX IF NOT EXISTS idx_videos_group ON videos(content_group_id);
            CREATE INDEX IF NOT EXISTS idx_x_edges_source ON x_account_edges(source_account_id);
            CREATE INDEX IF NOT EXISTS idx_x_edges_target ON x_account_edges(target_account_id);
            """
        )


def add_source(
    platform: str,
    target_type: str,
    target_value: str,
    crawl_interval_seconds: int = 3600,
    enabled: bool = True,
) -> int:
    now = utc_now_iso()
    with connect() as conn:
        existing = conn.execute(
            """
            SELECT id FROM source_targets
            WHERE platform = ? AND target_type = ? AND target_value = ?
            """,
            (platform, target_type, target_value),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE source_targets
                SET crawl_interval_seconds = ?, enabled = ?, updated_at = ?
                WHERE id = ?
                """,
                (crawl_interval_seconds, int(enabled), now, existing["id"]),
            )
            return int(existing["id"])
        cursor = conn.execute(
            """
            INSERT INTO source_targets (
                platform, target_type, target_value, crawl_interval_seconds,
                enabled, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                platform,
                target_type,
                target_value,
                crawl_interval_seconds,
                int(enabled),
                now,
                now,
            ),
        )
        return int(cursor.lastrowid)


def list_sources(enabled_only: bool = False) -> list[dict[str, Any]]:
    where = "WHERE enabled = 1" if enabled_only else ""
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM source_targets
            {where}
            ORDER BY id DESC
            """
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_source(source_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM source_targets WHERE id = ?", (source_id,)).fetchone()
    return _row_to_dict(row) if row else None


def mark_source_result(source_id: int, error: str | None = None) -> None:
    now = utc_now_iso()
    with connect() as conn:
        conn.execute(
            """
            UPDATE source_targets
            SET last_crawled_at = ?, last_error = ?, updated_at = ?
            WHERE id = ?
            """,
            (now, error, now, source_id),
        )


def upsert_candidate(
    candidate: CandidateVideo,
    target_type: str | None = None,
    fetched_at: str | None = None,
) -> tuple[int, int, bool]:
    now = utc_now_iso()
    item_id = candidate.platform_item_id or candidate.media_url or candidate.source_url
    fetched = fetched_at or now

    with connect() as conn:
        existing = conn.execute(
            """
            SELECT id, video_id FROM video_occurrences
            WHERE platform = ? AND platform_item_id = ?
            """,
            (candidate.platform, item_id),
        ).fetchone()
        if existing:
            return int(existing["video_id"]), int(existing["id"]), False

        existing_by_url = conn.execute(
            """
            SELECT id, video_id FROM video_occurrences
            WHERE platform = ? AND source_url = ?
            ORDER BY id
            LIMIT 1
            """,
            (candidate.platform, candidate.source_url),
        ).fetchone()
        if existing_by_url:
            return int(existing_by_url["video_id"]), int(existing_by_url["id"]), False

        video_cursor = conn.execute(
            """
            INSERT INTO videos (title, description, status, created_at, updated_at)
            VALUES (?, ?, 'discovered', ?, ?)
            """,
            (candidate.title, candidate.description, now, now),
        )
        video_id = int(video_cursor.lastrowid)

        occurrence_cursor = conn.execute(
            """
            INSERT INTO video_occurrences (
                video_id, platform, target_type, source_url, media_url, platform_item_id,
                author_name, published_at, first_seen_at, fetched_at, raw_text,
                raw_metadata_json, confidence_score, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                video_id,
                candidate.platform,
                target_type,
                candidate.source_url,
                candidate.media_url,
                item_id,
                candidate.author_name,
                candidate.published_at,
                now,
                fetched,
                candidate.text,
                json.dumps(candidate.raw_metadata, ensure_ascii=False),
                candidate.confidence_score,
                now,
                now,
            ),
        )
        occurrence_id = int(occurrence_cursor.lastrowid)

        conn.execute(
            """
            INSERT INTO source_evidence (
                occurrence_id, evidence_type, evidence_url, extracted_time,
                confidence_score, raw_payload_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                occurrence_id,
                candidate.evidence_type,
                candidate.source_url,
                candidate.published_at,
                candidate.confidence_score,
                json.dumps(candidate.raw_metadata, ensure_ascii=False),
                now,
            ),
        )
        return video_id, occurrence_id, True


def update_video_storage(video_id: int, storage_path: str | None, status: str) -> None:
    now = utc_now_iso()
    with connect() as conn:
        conn.execute(
            """
            UPDATE videos
            SET storage_path = ?, status = ?, updated_at = ?
            WHERE id = ?
            """,
            (storage_path, status, now, video_id),
        )


def update_video_analysis(
    video_id: int,
    *,
    file_sha256: str | None,
    duration_seconds: float | None,
    width: int | None,
    height: int | None,
    frame_hashes: list[str],
    status: str = "analyzed",
) -> None:
    now = utc_now_iso()
    with connect() as conn:
        conn.execute(
            """
            UPDATE videos
            SET file_sha256 = ?, duration_seconds = ?, width = ?, height = ?,
                status = ?, updated_at = ?
            WHERE id = ?
            """,
            (file_sha256, duration_seconds, width, height, status, now, video_id),
        )
        conn.execute(
            """
            INSERT INTO video_fingerprints (
                video_id, file_sha256, frame_hashes_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                file_sha256 = excluded.file_sha256,
                frame_hashes_json = excluded.frame_hashes_json,
                updated_at = excluded.updated_at
            """,
            (video_id, file_sha256, json.dumps(frame_hashes), now, now),
        )


def list_videos(limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                v.*,
                o.platform,
                o.source_url,
                o.media_url,
                o.published_at,
                o.first_seen_at,
                o.author_name,
                o.raw_metadata_json,
                cg.duplicate_count,
                cg.confidence_score AS group_confidence_score,
                eo.platform AS earliest_platform,
                eo.source_url AS earliest_source_url,
                eo.published_at AS earliest_published_at,
                eo.first_seen_at AS earliest_first_seen_at,
                tc.label AS topic_label,
                vml.origin_label AS manual_origin_label,
                vml.notes AS manual_notes
            FROM videos v
            LEFT JOIN video_occurrences o ON o.video_id = v.id
            LEFT JOIN content_groups cg ON cg.id = v.content_group_id
            LEFT JOIN video_occurrences eo ON eo.id = cg.earliest_occurrence_id
            LEFT JOIN video_cluster_links vcl ON vcl.video_id = v.id
            LEFT JOIN topic_clusters tc ON tc.id = vcl.cluster_id
            LEFT JOIN video_manual_labels vml ON vml.video_id = v.id
            GROUP BY v.id
            ORDER BY v.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_decorate_video_summary(_row_to_dict(row)) for row in rows]


def get_video_detail(video_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        video_row = conn.execute(
            """
            SELECT
                v.*,
                cg.duplicate_count,
                cg.confidence_score AS group_confidence_score,
                eo.platform AS earliest_platform,
                eo.source_url AS earliest_source_url,
                eo.published_at AS earliest_published_at,
                eo.first_seen_at AS earliest_first_seen_at,
                tc.label AS topic_label,
                vcl.score AS topic_score,
                vml.origin_label AS manual_origin_label,
                vml.notes AS manual_notes
            FROM videos v
            LEFT JOIN content_groups cg ON cg.id = v.content_group_id
            LEFT JOIN video_occurrences eo ON eo.id = cg.earliest_occurrence_id
            LEFT JOIN video_cluster_links vcl ON vcl.video_id = v.id
            LEFT JOIN topic_clusters tc ON tc.id = vcl.cluster_id
            LEFT JOIN video_manual_labels vml ON vml.video_id = v.id
            WHERE v.id = ?
            """,
            (video_id,),
        ).fetchone()
        if not video_row:
            return None

        occurrence_rows = conn.execute(
            """
            SELECT * FROM video_occurrences
            WHERE video_id = ?
            ORDER BY COALESCE(published_at, first_seen_at), id
            """,
            (video_id,),
        ).fetchall()
        evidence_rows = conn.execute(
            """
            SELECT se.*
            FROM source_evidence se
            JOIN video_occurrences o ON o.id = se.occurrence_id
            WHERE o.video_id = ?
            ORDER BY se.confidence_score DESC, se.id
            """,
            (video_id,),
        ).fetchall()
        group_rows = []
        if video_row["content_group_id"]:
            group_rows = conn.execute(
                """
                SELECT id, title, status, platform, source_url, media_url, published_at
                FROM (
                    SELECT
                        v.id,
                        v.title,
                        v.status,
                        o.platform,
                        o.source_url,
                        o.media_url,
                        o.published_at
                    FROM videos v
                    LEFT JOIN video_occurrences o ON o.video_id = v.id
                    WHERE v.content_group_id = ?
                    GROUP BY v.id
                    ORDER BY v.id DESC
                )
                """,
                (video_row["content_group_id"],),
            ).fetchall()

    occurrences = [_decorate_occurrence(_row_to_dict(row)) for row in occurrence_rows]
    video = _decorate_video_summary(
        {
            **_row_to_dict(video_row),
            "platform": occurrences[0]["platform"] if occurrences else None,
            "source_url": occurrences[0]["source_url"] if occurrences else None,
            "media_url": occurrences[0]["media_url"] if occurrences else None,
            "published_at": occurrences[0]["published_at"] if occurrences else None,
            "first_seen_at": occurrences[0]["first_seen_at"] if occurrences else None,
            "author_name": occurrences[0]["author_name"] if occurrences else None,
            "raw_metadata_json": occurrence_rows[0]["raw_metadata_json"] if occurrence_rows else "{}",
        }
    )
    return {
        **video,
        "occurrences": occurrences,
        "evidence": [_decorate_evidence(_row_to_dict(row)) for row in evidence_rows],
        "group_videos": [_decorate_group_video(_row_to_dict(row)) for row in group_rows],
    }


def get_video_stream_info(video_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT
                v.id,
                v.status,
                v.storage_path,
                o.media_url,
                o.source_url,
                o.platform
            FROM videos v
            LEFT JOIN video_occurrences o ON o.video_id = v.id
            WHERE v.id = ?
            ORDER BY CASE WHEN o.media_url IS NOT NULL THEN 0 ELSE 1 END, o.id
            LIMIT 1
            """,
            (video_id,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_x_videos_needing_media(limit: int = 50) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                v.id,
                v.title,
                v.description,
                v.status,
                v.storage_path,
                o.id AS occurrence_id,
                o.source_url,
                o.media_url,
                o.raw_metadata_json
            FROM videos v
            JOIN video_occurrences o ON o.video_id = v.id
            WHERE o.platform = 'x'
              AND (
                o.media_url IS NULL
                OR o.media_url = ''
                OR o.media_url LIKE 'blob:%'
                OR (v.status = 'x_download_retryable' AND v.storage_path IS NULL)
              )
              AND v.status NOT IN ('x_media_unresolved', 'x_media_resolve_failed', 'safety_review')
            GROUP BY v.id
            ORDER BY v.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def update_x_video_media_url(
    video_id: int,
    media_url: str,
    *,
    resolver_payload: dict[str, Any] | None = None,
) -> None:
    now = utc_now_iso()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, raw_metadata_json
            FROM video_occurrences
            WHERE video_id = ? AND platform = 'x'
            ORDER BY id
            LIMIT 1
            """,
            (video_id,),
        ).fetchone()
        if not row:
            return
        raw = _json_loads(row["raw_metadata_json"], {})
        if resolver_payload:
            raw["resolved_media"] = resolver_payload
        conn.execute(
            """
            UPDATE video_occurrences
            SET media_url = ?, raw_metadata_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (media_url, json.dumps(raw, ensure_ascii=False), now, row["id"]),
        )


def list_occurrences(limit: int = 200) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM video_occurrences
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def videos_for_grouping() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                v.id, v.file_sha256, v.duration_seconds, v.created_at,
                fp.frame_hashes_json
            FROM videos v
            LEFT JOIN video_fingerprints fp ON fp.video_id = v.id
            ORDER BY v.id ASC
            """
        ).fetchall()
    result = []
    for row in rows:
        item = _row_to_dict(row)
        item["frame_hashes"] = _json_loads(item.pop("frame_hashes_json", None), [])
        result.append(item)
    return result


def occurrences_for_video_ids(video_ids: list[int]) -> list[dict[str, Any]]:
    if not video_ids:
        return []
    placeholders = ",".join("?" for _ in video_ids)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM video_occurrences
            WHERE video_id IN ({placeholders})
            ORDER BY id ASC
            """,
            video_ids,
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def rebuild_content_groups(groups: list[dict[str, Any]]) -> None:
    now = utc_now_iso()
    with connect() as conn:
        conn.execute("UPDATE videos SET content_group_id = NULL")
        conn.execute("DELETE FROM content_groups")
        for group in groups:
            cursor = conn.execute(
                """
                INSERT INTO content_groups (
                    canonical_video_id, earliest_occurrence_id, duplicate_count,
                    confidence_score, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    group["canonical_video_id"],
                    group["earliest_occurrence_id"],
                    group["duplicate_count"],
                    group["confidence_score"],
                    now,
                    now,
                ),
            )
            group_id = int(cursor.lastrowid)
            for video_id in group["video_ids"]:
                conn.execute(
                    "UPDATE videos SET content_group_id = ?, updated_at = ? WHERE id = ?",
                    (group_id, now, video_id),
                )


def list_content_groups(limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                cg.*,
                v.title AS canonical_title,
                o.platform AS earliest_platform,
                o.source_url AS earliest_source_url,
                o.published_at AS earliest_published_at,
                o.first_seen_at AS earliest_first_seen_at
            FROM content_groups cg
            LEFT JOIN videos v ON v.id = cg.canonical_video_id
            LEFT JOIN video_occurrences o ON o.id = cg.earliest_occurrence_id
            ORDER BY cg.duplicate_count DESC, cg.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def videos_for_clustering() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                v.id,
                v.title,
                v.description,
                GROUP_CONCAT(COALESCE(o.raw_text, ''), ' ') AS occurrence_text
            FROM videos v
            LEFT JOIN video_occurrences o ON o.video_id = v.id
            GROUP BY v.id
            ORDER BY v.id ASC
            """
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def rebuild_topic_clusters(clusters: list[dict[str, Any]]) -> None:
    now = utc_now_iso()
    with connect() as conn:
        conn.execute("DELETE FROM video_cluster_links")
        conn.execute("DELETE FROM topic_clusters")
        for cluster in clusters:
            cursor = conn.execute(
                """
                INSERT INTO topic_clusters (label, keywords_json, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    cluster["label"],
                    json.dumps(cluster["keywords"], ensure_ascii=False),
                    now,
                    now,
                ),
            )
            cluster_id = int(cursor.lastrowid)
            for video_id, score in cluster["videos"]:
                conn.execute(
                    """
                    INSERT INTO video_cluster_links (video_id, cluster_id, score)
                    VALUES (?, ?, ?)
                    """,
                    (video_id, cluster_id, score),
                )


def list_topic_clusters(limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                tc.*,
                COUNT(vcl.video_id) AS video_count
            FROM topic_clusters tc
            LEFT JOIN video_cluster_links vcl ON vcl.cluster_id = tc.id
            GROUP BY tc.id
            ORDER BY video_count DESC, tc.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    result = []
    for row in rows:
        item = _row_to_dict(row)
        item["keywords"] = _json_loads(item.pop("keywords_json", None), [])
        result.append(item)
    return result


def upsert_x_account(
    *,
    handle: str,
    display_name: str | None = None,
    profile_url: str | None = None,
    avatar_url: str | None = None,
    account_kind: str = "person",
    bookmarked_posts: int = 0,
    bookmarked_video_posts: int = 0,
    timeline_posts: int = 0,
    timeline_video_posts: int = 0,
    own_posts: int = 0,
    declared_reposts: int = 0,
    likely_non_original_posts: int = 0,
    possible_non_original_posts: int = 0,
    originality_label: str = "unknown",
    raw_metadata: dict[str, Any] | None = None,
) -> int:
    normalized = normalize_x_handle(handle)
    if not normalized:
        raise ValueError("handle is required")
    now = utc_now_iso()
    raw_json = json.dumps(raw_metadata or {}, ensure_ascii=False)
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO x_accounts (
                handle, display_name, profile_url, avatar_url, account_kind,
                bookmarked_posts, bookmarked_video_posts, timeline_posts,
                timeline_video_posts, own_posts, declared_reposts,
                likely_non_original_posts, possible_non_original_posts,
                originality_label, raw_metadata_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(handle) DO UPDATE SET
                display_name = COALESCE(excluded.display_name, x_accounts.display_name),
                profile_url = COALESCE(excluded.profile_url, x_accounts.profile_url),
                avatar_url = COALESCE(excluded.avatar_url, x_accounts.avatar_url),
                account_kind = CASE
                    WHEN excluded.account_kind != 'person' THEN excluded.account_kind
                    ELSE x_accounts.account_kind
                END,
                bookmarked_posts = MAX(x_accounts.bookmarked_posts, excluded.bookmarked_posts),
                bookmarked_video_posts = MAX(x_accounts.bookmarked_video_posts, excluded.bookmarked_video_posts),
                timeline_posts = MAX(x_accounts.timeline_posts, excluded.timeline_posts),
                timeline_video_posts = MAX(x_accounts.timeline_video_posts, excluded.timeline_video_posts),
                own_posts = MAX(x_accounts.own_posts, excluded.own_posts),
                declared_reposts = MAX(x_accounts.declared_reposts, excluded.declared_reposts),
                likely_non_original_posts = MAX(x_accounts.likely_non_original_posts, excluded.likely_non_original_posts),
                possible_non_original_posts = MAX(x_accounts.possible_non_original_posts, excluded.possible_non_original_posts),
                originality_label = CASE
                    WHEN excluded.originality_label != 'unknown' THEN excluded.originality_label
                    ELSE x_accounts.originality_label
                END,
                raw_metadata_json = CASE
                    WHEN excluded.raw_metadata_json != '{}' THEN excluded.raw_metadata_json
                    ELSE x_accounts.raw_metadata_json
                END,
                updated_at = excluded.updated_at
            RETURNING id
            """,
            (
                normalized,
                display_name,
                profile_url or x_profile_url(normalized),
                avatar_url,
                account_kind,
                bookmarked_posts,
                bookmarked_video_posts,
                timeline_posts,
                timeline_video_posts,
                own_posts,
                declared_reposts,
                likely_non_original_posts,
                possible_non_original_posts,
                originality_label,
                raw_json,
                now,
                now,
            ),
        )
        return int(cursor.fetchone()["id"])


def upsert_x_account_edge(
    *,
    source_handle: str,
    target_handle: str,
    relationship_type: str,
    weight: int = 1,
    evidence_url: str | None = None,
    raw_metadata: dict[str, Any] | None = None,
) -> int:
    source = normalize_x_handle(source_handle)
    target = normalize_x_handle(target_handle)
    if not source or not target:
        raise ValueError("source_handle and target_handle are required")
    if source.lower() == target.lower() and relationship_type != "bookmarked_author":
        raise ValueError("self edges are not useful for the account graph")
    source_id = upsert_x_account(handle=source)
    target_id = upsert_x_account(handle=target)
    now = utc_now_iso()
    raw_json = json.dumps(raw_metadata or {}, ensure_ascii=False)
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO x_account_edges (
                source_account_id, target_account_id, relationship_type,
                weight, evidence_url, raw_metadata_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_account_id, target_account_id, relationship_type, evidence_url)
            DO UPDATE SET
                weight = MAX(x_account_edges.weight, excluded.weight),
                raw_metadata_json = CASE
                    WHEN excluded.raw_metadata_json != '{}' THEN excluded.raw_metadata_json
                    ELSE x_account_edges.raw_metadata_json
                END,
                updated_at = excluded.updated_at
            RETURNING id
            """,
            (source_id, target_id, relationship_type, max(1, weight), evidence_url, raw_json, now, now),
        )
        return int(cursor.fetchone()["id"])


def update_x_account_label(handle: str, manual_label: str, notes: str | None = None) -> dict[str, Any]:
    normalized = normalize_x_handle(handle)
    if not normalized:
        raise ValueError("handle is required")
    now = utc_now_iso()
    upsert_x_account(handle=normalized)
    with connect() as conn:
        conn.execute(
            """
            UPDATE x_accounts
            SET manual_label = ?, notes = ?, updated_at = ?
            WHERE handle = ?
            """,
            (manual_label, notes, now, normalized),
        )
    account = get_x_account(normalized)
    if not account:
        raise ValueError(f"account not found: {normalized}")
    return account


def update_video_manual_label(video_id: int, origin_label: str, notes: str | None = None) -> dict[str, Any] | None:
    now = utc_now_iso()
    with connect() as conn:
        exists = conn.execute("SELECT id FROM videos WHERE id = ?", (video_id,)).fetchone()
        if not exists:
            return None
        conn.execute(
            """
            INSERT INTO video_manual_labels (video_id, origin_label, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                origin_label = excluded.origin_label,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            (video_id, origin_label, notes, now, now),
        )
    return get_video_detail(video_id)


def list_x_account_graph(
    *,
    relationship_types: list[str] | None = None,
    hide_single_edge_nodes: bool = True,
) -> dict[str, Any]:
    placeholders = ""
    params: list[Any] = []
    if relationship_types:
        placeholders = "WHERE e.relationship_type IN (" + ",".join("?" for _ in relationship_types) + ")"
        params = relationship_types

    with connect() as conn:
        edge_rows = conn.execute(
            f"""
            SELECT
                e.relationship_type,
                SUM(e.weight) AS weight,
                MIN(e.evidence_url) AS sample_evidence_url,
                sa.handle AS source_handle,
                ta.handle AS target_handle
            FROM x_account_edges e
            JOIN x_accounts sa ON sa.id = e.source_account_id
            JOIN x_accounts ta ON ta.id = e.target_account_id
            {placeholders}
            GROUP BY e.relationship_type, sa.handle, ta.handle
            ORDER BY weight DESC, source_handle, target_handle
            """,
            params,
        ).fetchall()
        account_rows = conn.execute("SELECT * FROM x_accounts ORDER BY handle COLLATE NOCASE").fetchall()

    video_counts = _x_video_counts_by_handle()
    accounts = {_row_to_dict(row)["handle"]: _decorate_x_account(_row_to_dict(row), video_counts) for row in account_rows}
    degree: dict[str, dict[str, int]] = {
        handle: {"in": 0, "out": 0, "total": 0} for handle in accounts
    }
    edges: list[dict[str, Any]] = []
    for row in edge_rows:
        item = _row_to_dict(row)
        source = item["source_handle"]
        target = item["target_handle"]
        degree.setdefault(source, {"in": 0, "out": 0, "total": 0})
        degree.setdefault(target, {"in": 0, "out": 0, "total": 0})
        degree[source]["out"] += 1
        degree[source]["total"] += 1
        degree[target]["in"] += 1
        degree[target]["total"] += 1
        edges.append(
            {
                "source": source,
                "target": target,
                "type": item["relationship_type"],
                "weight": int(item["weight"] or 1),
                "sample_evidence_url": item["sample_evidence_url"],
            }
        )

    visible_handles = set(accounts)
    if hide_single_edge_nodes:
        visible_handles = {
            handle
            for handle, item in accounts.items()
            if item["account_kind"] == "collection" or degree.get(handle, {}).get("total", 0) > 1
        }
        edges = [edge for edge in edges if edge["source"] in visible_handles and edge["target"] in visible_handles]
        connected = {edge["source"] for edge in edges} | {edge["target"] for edge in edges}
        visible_handles = {
            handle
            for handle in visible_handles
            if handle in connected or accounts[handle]["account_kind"] == "collection"
        }

    nodes = []
    for handle in sorted(visible_handles, key=str.lower):
        account = accounts[handle]
        d = degree.get(handle, {"in": 0, "out": 0, "total": 0})
        nodes.append({**account, "in_degree": d["in"], "out_degree": d["out"], "degree": d["total"]})

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "total_accounts": len(accounts),
            "visible_accounts": len(nodes),
            "total_edges": len(edge_rows),
            "visible_edges": len(edges),
            "hidden_single_edge_nodes": max(0, len(accounts) - len(nodes)),
            "relationship_types": sorted({edge["type"] for edge in edges}),
        },
    }


def get_x_account(handle: str) -> dict[str, Any] | None:
    normalized = normalize_x_handle(handle)
    if not normalized:
        return None
    with connect() as conn:
        row = conn.execute("SELECT * FROM x_accounts WHERE handle = ?", (normalized,)).fetchone()
        if not row:
            return None
        outgoing = conn.execute(
            """
            SELECT
                e.relationship_type,
                SUM(e.weight) AS weight,
                MIN(e.evidence_url) AS sample_evidence_url,
                ta.handle AS handle,
                ta.display_name AS display_name,
                ta.profile_url AS profile_url
            FROM x_account_edges e
            JOIN x_accounts sa ON sa.id = e.source_account_id
            JOIN x_accounts ta ON ta.id = e.target_account_id
            WHERE sa.handle = ?
            GROUP BY e.relationship_type, ta.handle
            ORDER BY weight DESC, ta.handle COLLATE NOCASE
            LIMIT 80
            """,
            (normalized,),
        ).fetchall()
        incoming = conn.execute(
            """
            SELECT
                e.relationship_type,
                SUM(e.weight) AS weight,
                MIN(e.evidence_url) AS sample_evidence_url,
                sa.handle AS handle,
                sa.display_name AS display_name,
                sa.profile_url AS profile_url
            FROM x_account_edges e
            JOIN x_accounts sa ON sa.id = e.source_account_id
            JOIN x_accounts ta ON ta.id = e.target_account_id
            WHERE ta.handle = ?
            GROUP BY e.relationship_type, sa.handle
            ORDER BY weight DESC, sa.handle COLLATE NOCASE
            LIMIT 80
            """,
            (normalized,),
        ).fetchall()

    video_counts = _x_video_counts_by_handle()
    account = _decorate_x_account(_row_to_dict(row), video_counts)
    account["videos"] = _x_videos_for_handle(normalized)
    account["outgoing"] = [_row_to_dict(item) for item in outgoing]
    account["incoming"] = [_row_to_dict(item) for item in incoming]
    return account


def normalize_x_handle(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    stripped = stripped.removeprefix("@")
    if stripped.startswith("https://x.com/"):
        stripped = stripped.split("https://x.com/", 1)[1].split("/", 1)[0]
    return stripped.strip("@/ ") or None


def x_profile_url(handle: str) -> str:
    normalized = normalize_x_handle(handle) or handle
    return f"https://x.com/{normalized}"


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _decorate_x_account(item: dict[str, Any], video_counts: dict[str, int]) -> dict[str, Any]:
    raw = _json_loads(item.pop("raw_metadata_json", None), {})
    handle = item["handle"]
    item["profile_url"] = item.get("profile_url") or x_profile_url(handle)
    item["video_count"] = video_counts.get(handle.lower(), 0)
    item["raw_metadata"] = raw
    item["effective_label"] = item.get("manual_label") or item.get("originality_label") or "unknown"
    item["risk_score"] = (
        int(item.get("likely_non_original_posts") or 0) * 2
        + int(item.get("possible_non_original_posts") or 0)
        + int(item.get("declared_reposts") or 0)
    )
    return item


def _x_video_counts_by_handle() -> dict[str, int]:
    counts: dict[str, set[int]] = {}
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT o.video_id, o.author_name, o.raw_metadata_json
            FROM video_occurrences o
            WHERE o.platform = 'x'
            """
        ).fetchall()
    for row in rows:
        raw = _json_loads(row["raw_metadata_json"], {})
        handle = _handle_from_raw(raw, row["author_name"])
        if not handle:
            continue
        counts.setdefault(handle.lower(), set()).add(int(row["video_id"]))
    return {handle: len(video_ids) for handle, video_ids in counts.items()}


def _x_videos_for_handle(handle: str, limit: int = 120) -> list[dict[str, Any]]:
    normalized = normalize_x_handle(handle)
    if not normalized:
        return []
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                v.*,
                o.platform,
                o.source_url,
                o.media_url,
                o.published_at,
                o.first_seen_at,
                o.author_name,
                o.raw_metadata_json,
                cg.duplicate_count,
                cg.confidence_score AS group_confidence_score,
                eo.platform AS earliest_platform,
                eo.source_url AS earliest_source_url,
                eo.published_at AS earliest_published_at,
                eo.first_seen_at AS earliest_first_seen_at,
                tc.label AS topic_label,
                vml.origin_label AS manual_origin_label,
                vml.notes AS manual_notes
            FROM videos v
            JOIN video_occurrences o ON o.video_id = v.id
            LEFT JOIN content_groups cg ON cg.id = v.content_group_id
            LEFT JOIN video_occurrences eo ON eo.id = cg.earliest_occurrence_id
            LEFT JOIN video_cluster_links vcl ON vcl.video_id = v.id
            LEFT JOIN topic_clusters tc ON tc.id = vcl.cluster_id
            LEFT JOIN video_manual_labels vml ON vml.video_id = v.id
            WHERE o.platform = 'x'
            ORDER BY COALESCE(o.published_at, o.first_seen_at) DESC, v.id DESC
            """,
        ).fetchall()
    result = []
    seen: set[int] = set()
    for row in rows:
        item = _row_to_dict(row)
        raw = _json_loads(item.get("raw_metadata_json"), {})
        row_handle = _handle_from_raw(raw, item.get("author_name"))
        if not row_handle or row_handle.lower() != normalized.lower():
            continue
        video_id = int(item["id"])
        if video_id in seen:
            continue
        seen.add(video_id)
        result.append(_decorate_video_summary(item))
        if len(result) >= limit:
            break
    return result


def _handle_from_raw(raw: Any, fallback_name: Any = None) -> str | None:
    if isinstance(raw, dict):
        direct = normalize_x_handle(raw.get("author_handle") or raw.get("article_handle") or raw.get("target_handle"))
        if direct:
            return direct
        user = raw.get("user")
        if isinstance(user, dict):
            direct = normalize_x_handle(user.get("username") or user.get("screen_name"))
            if direct:
                return direct
        tweet = raw.get("tweet")
        if isinstance(tweet, dict):
            direct = normalize_x_handle(tweet.get("author_handle") or tweet.get("username"))
            if direct:
                return direct
    return normalize_x_handle(fallback_name)


def _decorate_video_summary(item: dict[str, Any]) -> dict[str, Any]:
    raw = _json_loads(item.pop("raw_metadata_json", None), {})
    item["title"] = _clean_text(item.get("title"))
    item["description"] = _clean_text(item.get("description"))
    item["thumbnail_url"] = _thumbnail_from_raw(raw)
    item["author_handle"] = _handle_from_raw(raw)
    item["author_profile_url"] = x_profile_url(item["author_handle"]) if item.get("author_handle") else None
    item["origin_label"] = item.get("manual_origin_label") or "unknown"
    item["origin_notes"] = item.get("manual_notes")
    blocked_playback = item.get("status") == "safety_review"
    item["has_playback"] = bool(
        not blocked_playback and (item.get("storage_path") or _is_playable_media_url(item.get("media_url")))
    )
    item["playback_url"] = f"/api/videos/{item['id']}/stream" if item["has_playback"] else None
    item["display_time"] = item.get("published_at") or item.get("first_seen_at")
    item["earliest_time"] = item.get("earliest_published_at") or item.get("earliest_first_seen_at")
    return item


def _decorate_occurrence(item: dict[str, Any]) -> dict[str, Any]:
    raw = _json_loads(item.pop("raw_metadata_json", None), {})
    item["thumbnail_url"] = _thumbnail_from_raw(raw)
    item["has_playback"] = _is_playable_media_url(item.get("media_url"))
    item["author_handle"] = _handle_from_raw(raw, item.get("author_name"))
    item["author_profile_url"] = x_profile_url(item["author_handle"]) if item.get("author_handle") else None
    item["raw_metadata"] = raw
    return item


def _decorate_evidence(item: dict[str, Any]) -> dict[str, Any]:
    item["raw_payload"] = _json_loads(item.pop("raw_payload_json", None), {})
    return item


def _decorate_group_video(item: dict[str, Any]) -> dict[str, Any]:
    item["title"] = _clean_text(item.get("title"))
    item["has_playback"] = item.get("status") != "safety_review" and _is_playable_media_url(
        item.get("media_url")
    )
    item["playback_url"] = f"/api/videos/{item['id']}/stream" if item["has_playback"] else None
    return item


def _clean_text(value: Any) -> Any:
    if isinstance(value, str):
        return unescape(value).strip()
    return value


def _is_playable_media_url(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    return not value.startswith("blob:")


def _thumbnail_from_raw(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("thumbnail_url", "preview_image_url", "poster", "thumbnailUrl", "url"):
            found = value.get(key)
            if isinstance(found, str) and _looks_like_image(found):
                return found
            if isinstance(found, list):
                for item in found:
                    if isinstance(item, str) and _looks_like_image(item):
                        return item
        for nested in value.values():
            found = _thumbnail_from_raw(nested)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _thumbnail_from_raw(item)
            if found:
                return found
    return None


def _looks_like_image(value: str) -> bool:
    lowered = value.lower()
    return (
        lowered.startswith("http://")
        or lowered.startswith("https://")
    ) and any(token in lowered for token in (".jpg", ".jpeg", ".png", ".webp", "format=jpg", "format=png", "thumb"))
