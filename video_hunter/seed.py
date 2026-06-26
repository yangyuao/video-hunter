"""Generate demonstration knowledge-graph data so the UI has something to show.

The real data pipeline ingests X bookmarks / timelines / follow graphs from
exported JSON. Until those exist, this module seeds a realistic, community-
structured graph: accounts grouped into communities, dense following within a
community and sparse across, a few original-content "hubs" that many accounts
repost (the provenance chain), plus videos with some shared-content groups that
mimic re-upload (搬运) clusters.

It is deterministic (seeded RNG) and idempotent — upserts mean re-running just
tops up metadata. Invoke via ``python -m video_hunter seed-demo``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from video_hunter import db
from video_hunter.clustering import rebuild_topic_clusters
from video_hunter.connectors.base import CandidateVideo, utc_now_iso
from video_hunter.dedup import rebuild_duplicate_groups

LABELS_BY_ROLE = {
    "original": "likely_original",
    "curator": "likely_non_original",
    "mixer": "needs_review",
    "reposter": "reposter",
}

VIDEO_TOPICS = [
    ("科技", ["ai", "芯片", "机器人", "模型", "算力", "自动驾驶"]),
    ("生活", ["咖啡", "旅行", "美食", "vlog", "日常", "摄影"]),
    ("游戏", ["游戏", "通关", "攻略", "电竞", "实机"]),
    ("设计", ["设计", "ui", "排版", "字体", "品牌"]),
    ("金融", ["市场", "股票", "宏观", "周期", "利率"]),
]


@dataclass(frozen=True)
class SeedResult:
    accounts: int
    following_edges: int
    repost_edges: int
    bookmark_edges: int
    videos: int
    content_groups: int
    topic_clusters: int


def seed_demo(
    *,
    accounts: int = 60,
    communities: int = 5,
    videos: int = 120,
    seed: int = 7,
) -> SeedResult:
    db.init_db()
    rng = random.Random(seed)

    handles = _create_accounts(rng, accounts, communities)
    following_edges = _create_following(rng, handles, communities)
    repost_edges = _create_reposts(rng, handles)
    bookmark_edges = _create_bookmarks(rng, handles)
    video_count = _create_videos(rng, handles, videos)

    content_groups = len(rebuild_duplicate_groups())
    topic_clusters = len(rebuild_topic_clusters())
    return SeedResult(
        accounts=len(handles) + 1,  # +1 for the my_x_bookmarks collection
        following_edges=following_edges,
        repost_edges=repost_edges,
        bookmark_edges=bookmark_edges,
        videos=video_count,
        content_groups=content_groups,
        topic_clusters=topic_clusters,
    )


def _create_accounts(rng: random.Random, count: int, communities: int) -> list[dict[str, Any]]:
    handles: list[dict[str, Any]] = []
    for index in range(count):
        community = index % communities
        role = rng.choices(
            ["original", "curator", "mixer", "reposter"],
            weights=[0.4, 0.25, 0.2, 0.15],
        )[0]
        handle = f"creator_{community:02d}_{index:03d}"
        display_name = rng.choice(
            ["像素工坊", "深夜剪辑", "AerialLab", "极客速递", "潮汐视觉", "信号塔", "原野Vlog",
             "复盘笔记", "小宇宙", "光影手记", "脑波电台", "齿轮社", "南屿", "北纬四十", "拾光"]
        ) + f" {index}"
        timeline_posts = rng.randint(20, 400)
        own_posts = int(timeline_posts * rng.uniform(0.2, 0.9))
        declared_reposts = timeline_posts - own_posts
        likely = 0
        possible = 0
        if role == "curator":
            likely = rng.randint(5, 40)
            possible = rng.randint(5, 30)
        elif role == "mixer":
            possible = rng.randint(8, 40)
        bookmarked_posts = rng.randint(0, 60)

        db.upsert_x_account(
            handle=handle,
            display_name=display_name,
            account_kind="person",
            timeline_posts=timeline_posts,
            timeline_video_posts=int(timeline_posts * rng.uniform(0.1, 0.5)),
            own_posts=own_posts,
            declared_reposts=declared_reposts,
            likely_non_original_posts=likely,
            possible_non_original_posts=possible,
            bookmarked_posts=bookmarked_posts,
            bookmarked_video_posts=int(bookmarked_posts * rng.uniform(0.1, 0.6)),
            originality_label=LABELS_BY_ROLE[role],
            raw_metadata={"seed_role": role, "community": community},
        )
        handles.append({"handle": handle, "community": community, "role": role})
    return handles


def _create_following(rng: random.Random, handles: list[dict[str, Any]], communities: int) -> int:
    by_community: dict[int, list[str]] = {}
    for item in handles:
        by_community.setdefault(item["community"], []).append(item["handle"])

    edges = 0
    for item in handles:
        own = item["handle"]
        community = item["community"]
        same_pool = [h for h in by_community[community] if h != own]
        cross_pool = [h["handle"] for h in handles if h["community"] != community]
        following = set()
        for target in rng.sample(same_pool, k=min(len(same_pool), rng.randint(2, 6))):
            following.add(target)
        for target in rng.sample(cross_pool, k=min(len(cross_pool), rng.randint(0, 2))):
            following.add(target)
        for target in following:
            db.upsert_x_account_edge(
                source_handle=own,
                target_handle=target,
                relationship_type="following",
                evidence_url=f"https://x.com/{own}",
            )
            edges += 1
    return edges


def _create_reposts(rng: random.Random, handles: list[dict[str, Any]]) -> int:
    originals = [item for item in handles if item["role"] == "original"]
    if not originals:
        originals = handles[: max(1, len(handles) // 4)]
    hubs = [item["handle"] for item in originals[: max(3, len(originals) // 3)]]

    edges = 0
    for item in handles:
        own = item["handle"]
        if own in hubs and item["role"] == "original":
            continue
        targets = rng.sample(hubs, k=min(len(hubs), rng.randint(1, 3)))
        for hub in targets:
            if hub == own:
                continue
            db.upsert_x_account_edge(
                source_handle=own,
                target_handle=hub,
                relationship_type="reposted",
                weight=rng.randint(1, 4),
                evidence_url=f"https://x.com/{own}/status/{rng.randint(1000, 9999)}",
            )
            edges += 1
    return edges


def _create_bookmarks(rng: random.Random, handles: list[dict[str, Any]]) -> int:
    collection = "my_x_bookmarks"
    db.upsert_x_account(
        handle=collection,
        display_name="我的 X 书签",
        profile_url="https://x.com/i/bookmarks",
        account_kind="collection",
        raw_metadata={"source": "seed"},
    )
    bookmarked = rng.sample([item["handle"] for item in handles], k=min(len(handles), len(handles) * 4 // 5))
    for handle in bookmarked:
        db.upsert_x_account_edge(
            source_handle=collection,
            target_handle=handle,
            relationship_type="bookmarked_author",
            weight=rng.randint(1, 6),
            evidence_url=f"x-bookmarks://{handle}",
        )
    return len(bookmarked)


def _create_videos(rng: random.Random, handles: list[dict[str, Any]], count: int) -> int:
    fetched_at = utc_now_iso()
    # A small pool of "canonical" fingerprints — videos sharing one become a
    # content group (same content re-uploaded across accounts = 搬运 chain).
    canonical_hashes = [f"sha256:seed:{i:03d}" for i in range(count // 6 + 1)]
    created = 0

    for index in range(count):
        author = rng.choice(handles)
        handle = author["handle"]
        topic_label, keywords = rng.choice(VIDEO_TOPICS)
        title = f"{topic_label} · {rng.choice(keywords)} #{index}"
        status_url = f"https://x.com/{handle}/status/{9000000000000000000 + index}"
        candidate = CandidateVideo(
            platform="x",
            source_url=status_url,
            media_url=None,
            platform_item_id=f"seed:{index}",
            author_name=handle,
            title=title,
            description=title,
            text=rng.choice(keywords),
            published_at=f"2025-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}T{rng.randint(0, 23):02d}:00:00+00:00",
            thumbnail_url=None,
            evidence_type="seed_metadata",
            confidence_score=0.6,
            raw_metadata={
                "author_handle": handle,
                "article_handle": handle,
                "fetched_at": fetched_at,
                "seed_topic": topic_label,
            },
        )
        video_id, _occurrence_id, was_created = db.upsert_candidate(
            candidate, target_type="seed", fetched_at=fetched_at
        )
        if was_created:
            db.update_video_storage(video_id, None, "metadata_only")
        # Assign fingerprint: ~1/5 of videos reuse a canonical hash → content groups.
        if index % 5 == 0:
            sha = rng.choice(canonical_hashes)
            db.update_video_analysis(
                video_id,
                file_sha256=sha,
                duration_seconds=float(rng.randint(8, 120)),
                width=1920,
                height=1080,
                frame_hashes=[sha[-8:]] * 3,
                status="analyzed",
            )
        created += 1
    return created
