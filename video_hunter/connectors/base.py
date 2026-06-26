from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class SourceTarget:
    id: int
    platform: str
    target_type: str
    target_value: str
    crawl_interval_seconds: int = 3600
    enabled: bool = True


@dataclass(frozen=True)
class CrawlContext:
    fetched_at: str = field(default_factory=utc_now_iso)
    limit: int = 50


@dataclass(frozen=True)
class CandidateVideo:
    platform: str
    source_url: str
    media_url: str | None = None
    platform_item_id: str | None = None
    author_name: str | None = None
    title: str | None = None
    description: str | None = None
    text: str | None = None
    published_at: str | None = None
    thumbnail_url: str | None = None
    evidence_type: str = "metadata"
    confidence_score: float = 0.5
    raw_metadata: dict[str, Any] = field(default_factory=dict)


class Connector:
    def crawl(self, source: SourceTarget, context: CrawlContext) -> list[CandidateVideo]:
        raise NotImplementedError
