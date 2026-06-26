from __future__ import annotations

import re
from collections import Counter
from typing import Any

from video_hunter import db


STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "this",
    "that",
    "video",
    "watch",
    "official",
    "https",
    "http",
    "www",
    "一个",
    "这个",
    "视频",
    "发布",
    "官方",
    "观看",
}


def rebuild_topic_clusters() -> list[dict[str, Any]]:
    videos = db.videos_for_clustering()
    clusters: list[dict[str, Any]] = []

    for video in videos:
        text = " ".join(
            part
            for part in [
                video.get("title"),
                video.get("description"),
                video.get("occurrence_text"),
            ]
            if part
        )
        keywords = top_keywords(text)
        if not keywords:
            continue
        keyword_set = set(keywords)
        match = _find_cluster(clusters, keyword_set)
        if match is None:
            clusters.append(
                {
                    "keyword_sets": [keyword_set],
                    "keywords": keywords,
                    "videos": [(int(video["id"]), 1.0)],
                }
            )
        else:
            score = _jaccard(set(match["keywords"]), keyword_set)
            match["keyword_sets"].append(keyword_set)
            match["videos"].append((int(video["id"]), score))
            match["keywords"] = _merge_keywords(match["keyword_sets"])

    persisted = []
    for cluster in clusters:
        keywords = cluster["keywords"][:8]
        persisted.append(
            {
                "label": " / ".join(keywords[:3]),
                "keywords": keywords,
                "videos": cluster["videos"],
            }
        )

    db.rebuild_topic_clusters(persisted)
    return persisted


def top_keywords(text: str, limit: int = 8) -> list[str]:
    tokens = tokenize(text)
    counts = Counter(token for token in tokens if token not in STOPWORDS)
    return [token for token, _ in counts.most_common(limit)]


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    latin = re.findall(r"[a-z0-9][a-z0-9_-]{1,}", lowered)
    cjk_runs = re.findall(r"[\u4e00-\u9fff]{2,}", lowered)
    cjk_tokens: list[str] = []
    for run in cjk_runs:
        if len(run) <= 4:
            cjk_tokens.append(run)
        else:
            cjk_tokens.extend(run[index : index + 2] for index in range(len(run) - 1))
    return latin + cjk_tokens


def _find_cluster(clusters: list[dict[str, Any]], keyword_set: set[str]) -> dict[str, Any] | None:
    for cluster in clusters:
        existing = set(cluster["keywords"])
        if not existing:
            continue
        if _jaccard(existing, keyword_set) >= 0.25:
            return cluster
        if cluster["keywords"][0] in keyword_set:
            return cluster
    return None


def _merge_keywords(keyword_sets: list[set[str]]) -> list[str]:
    counts = Counter()
    for keyword_set in keyword_sets:
        counts.update(keyword_set)
    return [keyword for keyword, _ in counts.most_common(8)]


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)
