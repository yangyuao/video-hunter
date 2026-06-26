from __future__ import annotations

from video_hunter.connectors.base import CandidateVideo, Connector, CrawlContext, SourceTarget


class DirectVideoConnector(Connector):
    def crawl(self, source: SourceTarget, context: CrawlContext) -> list[CandidateVideo]:
        return [
            CandidateVideo(
                platform=source.platform,
                source_url=source.target_value,
                media_url=source.target_value,
                platform_item_id=source.target_value,
                title=source.target_value.rsplit("/", 1)[-1],
                evidence_type="direct_url",
                confidence_score=0.9,
                raw_metadata={
                    "source_id": source.id,
                    "target_type": source.target_type,
                    "fetched_at": context.fetched_at,
                },
            )
        ]
