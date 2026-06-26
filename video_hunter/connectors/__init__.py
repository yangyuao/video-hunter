from __future__ import annotations

from video_hunter.connectors.base import CandidateVideo, CrawlContext, SourceTarget


def get_connector(platform: str):
    normalized = platform.strip().lower()
    if normalized in {"direct", "video_url", "file"}:
        from video_hunter.connectors.direct import DirectVideoConnector

        return DirectVideoConnector()
    if normalized in {"webpage", "web", "site", "custom_site"}:
        from video_hunter.connectors.webpage import WebPageConnector

        return WebPageConnector()
    if normalized in {"91porn", "porn91", "91p"}:
        from video_hunter.connectors.porn91 import Porn91Connector

        return Porn91Connector()
    if normalized in {"x", "twitter"}:
        from video_hunter.connectors.x_api import XApiConnector

        return XApiConnector()
    raise ValueError(f"Unsupported platform: {platform}")


__all__ = [
    "CandidateVideo",
    "CrawlContext",
    "SourceTarget",
    "get_connector",
]
