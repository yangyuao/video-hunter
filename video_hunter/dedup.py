from __future__ import annotations

from datetime import datetime
from typing import Any

from video_hunter import db


def rebuild_duplicate_groups() -> list[dict[str, Any]]:
    videos = db.videos_for_grouping()
    groups: list[list[dict[str, Any]]] = []

    for video in videos:
        matched: list[dict[str, Any]] | None = None
        for group in groups:
            representative = group[0]
            if _is_duplicate(video, representative):
                matched = group
                break
        if matched is None:
            groups.append([video])
        else:
            matched.append(video)

    persisted_groups = []
    for group in groups:
        video_ids = [int(item["id"]) for item in group]
        occurrences = db.occurrences_for_video_ids(video_ids)
        earliest = _earliest_occurrence(occurrences)
        canonical_video_id = int(earliest["video_id"]) if earliest else int(group[0]["id"])
        persisted_groups.append(
            {
                "video_ids": video_ids,
                "canonical_video_id": canonical_video_id,
                "earliest_occurrence_id": int(earliest["id"]) if earliest else None,
                "duplicate_count": len(video_ids),
                "confidence_score": _group_confidence(group),
            }
        )

    db.rebuild_content_groups(persisted_groups)
    return persisted_groups


def _is_duplicate(video: dict[str, Any], representative: dict[str, Any]) -> bool:
    video_sha = video.get("file_sha256")
    rep_sha = representative.get("file_sha256")
    if video_sha and rep_sha and video_sha == rep_sha:
        return True

    video_hashes = video.get("frame_hashes") or []
    rep_hashes = representative.get("frame_hashes") or []
    if not video_hashes or not rep_hashes:
        return False

    duration_a = video.get("duration_seconds")
    duration_b = representative.get("duration_seconds")
    if duration_a and duration_b:
        longer = max(float(duration_a), float(duration_b))
        shorter = min(float(duration_a), float(duration_b))
        if longer > 0 and shorter / longer < 0.85:
            return False

    return frame_hash_similarity(video_hashes, rep_hashes) >= 0.82


def frame_hash_similarity(left: list[str], right: list[str]) -> float:
    if not left or not right:
        return 0.0
    scores = []
    for value in left:
        best = max(_single_hash_similarity(value, other) for other in right)
        scores.append(best)
    return sum(scores) / len(scores)


def _single_hash_similarity(left: str, right: str) -> float:
    try:
        a = int(left, 16)
        b = int(right, 16)
    except ValueError:
        return 0.0
    distance = (a ^ b).bit_count()
    return 1.0 - distance / 64


def _earliest_occurrence(occurrences: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not occurrences:
        return None
    return min(occurrences, key=_occurrence_sort_key)


def _occurrence_sort_key(occurrence: dict[str, Any]) -> tuple[datetime, int]:
    value = occurrence.get("published_at") or occurrence.get("first_seen_at")
    return (_parse_datetime(value), int(occurrence["id"]))


def _parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.max
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.max


def _group_confidence(group: list[dict[str, Any]]) -> float:
    if len(group) == 1:
        return 0.5
    if all(item.get("file_sha256") for item in group):
        return 0.95
    if any(item.get("frame_hashes") for item in group):
        return 0.8
    return 0.6
