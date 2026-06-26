from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from video_hunter import db


@dataclass(frozen=True)
class XFollowGraphImportResult:
    authors: int
    following_edges: int
    follower_edges: int
    skipped_edges: int


def import_x_follow_graph(path: Path) -> XFollowGraphImportResult:
    db.init_db()
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("authors", payload if isinstance(payload, list) else [])
    authors = 0
    following_edges = 0
    follower_edges = 0
    skipped_edges = 0

    for row in rows:
        handle = db.normalize_x_handle(row.get("handle"))
        if not handle:
            continue
        authors += 1
        db.upsert_x_account(
            handle=handle,
            display_name=row.get("display_name"),
            profile_url=row.get("profile_url") or db.x_profile_url(handle),
            raw_metadata={
                "follow_graph_source": str(path),
                "collected_at": row.get("collected_at") or payload.get("collected_at"),
                "following_count_observed": len(row.get("following") or []),
                "followers_count_observed": len(row.get("followers") or []),
                "errors": row.get("errors") or [],
            },
        )

        for followed in _handles(row.get("following")):
            if _upsert_following_edge(
                source_handle=handle,
                target_handle=followed,
                evidence_url=row.get("following_url") or f"https://x.com/{handle}/following",
                collected_at=row.get("collected_at") or payload.get("collected_at"),
                source_path=path,
            ):
                following_edges += 1
            else:
                skipped_edges += 1

        for follower in _handles(row.get("followers")):
            if _upsert_following_edge(
                source_handle=follower,
                target_handle=handle,
                evidence_url=row.get("followers_url") or f"https://x.com/{handle}/followers",
                collected_at=row.get("collected_at") or payload.get("collected_at"),
                source_path=path,
            ):
                follower_edges += 1
            else:
                skipped_edges += 1

    return XFollowGraphImportResult(
        authors=authors,
        following_edges=following_edges,
        follower_edges=follower_edges,
        skipped_edges=skipped_edges,
    )


def _upsert_following_edge(
    *,
    source_handle: str,
    target_handle: str,
    evidence_url: str,
    collected_at: str | None,
    source_path: Path,
) -> bool:
    try:
        db.upsert_x_account_edge(
            source_handle=source_handle,
            target_handle=target_handle,
            relationship_type="following",
            weight=1,
            evidence_url=evidence_url,
            raw_metadata={
                "source": str(source_path),
                "collected_at": collected_at,
            },
        )
    except ValueError:
        return False
    return True


def _handles(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        handle = None
        if isinstance(item, str):
            handle = db.normalize_x_handle(item)
        elif isinstance(item, dict):
            handle = db.normalize_x_handle(item.get("handle") or item.get("username") or item.get("url"))
            if handle:
                db.upsert_x_account(
                    handle=handle,
                    display_name=item.get("display_name") or item.get("name"),
                    profile_url=item.get("profile_url") or item.get("url") or db.x_profile_url(handle),
                    avatar_url=item.get("avatar_url"),
                    raw_metadata={"follow_graph_item": item},
                )
        if not handle:
            continue
        key = handle.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(handle)
    return result
