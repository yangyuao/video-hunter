from __future__ import annotations

from typing import Any

import httpx

from video_hunter.config import settings
from video_hunter.connectors.base import CandidateVideo, Connector, CrawlContext, SourceTarget


class XApiConnector(Connector):
    api_base = "https://api.x.com/2"

    def crawl(self, source: SourceTarget, context: CrawlContext) -> list[CandidateVideo]:
        if not settings.x_bearer_token:
            raise RuntimeError("X_BEARER_TOKEN is required for platform=x sources")

        target = source.target_value.strip().lstrip("@")
        with httpx.Client(
            base_url=self.api_base,
            headers={"Authorization": f"Bearer {settings.x_bearer_token}"},
            timeout=30,
        ) as client:
            user = self._resolve_user(client, target)
            tweets = self._fetch_tweets(client, user["id"], context.limit)

        includes = tweets.get("includes", {})
        media_by_key = {
            media["media_key"]: media for media in includes.get("media", []) if "media_key" in media
        }
        author_username = user.get("username") or target
        author_name = user.get("name") or author_username

        candidates: list[CandidateVideo] = []
        for tweet in tweets.get("data", []) or []:
            tweet_id = tweet.get("id")
            media_keys = (tweet.get("attachments") or {}).get("media_keys") or []
            for media_key in media_keys:
                media = media_by_key.get(media_key)
                if not media:
                    continue
                media_url = _select_media_url(media)
                if not media_url:
                    continue
                post_url = f"https://x.com/{author_username}/status/{tweet_id}"
                candidates.append(
                    CandidateVideo(
                        platform=source.platform,
                        source_url=post_url,
                        media_url=media_url,
                        platform_item_id=f"{tweet_id}:{media_key}",
                        author_name=author_name,
                        title=(tweet.get("text") or "")[:120],
                        description=tweet.get("text"),
                        text=tweet.get("text"),
                        published_at=tweet.get("created_at"),
                        thumbnail_url=media.get("preview_image_url") or media.get("url"),
                        evidence_type="x_api",
                        confidence_score=0.95,
                        raw_metadata={
                            "tweet": tweet,
                            "media": media,
                            "user": user,
                            "fetched_at": context.fetched_at,
                        },
                    )
                )
        return candidates

    def _resolve_user(self, client: httpx.Client, target: str) -> dict[str, Any]:
        if target.isdigit():
            response = client.get(
                f"/users/{target}",
                params={"user.fields": "created_at,description,username,name"},
            )
        else:
            response = client.get(
                f"/users/by/username/{target}",
                params={"user.fields": "created_at,description,username,name"},
            )
        response.raise_for_status()
        payload = response.json()
        if "data" not in payload:
            raise RuntimeError(f"X user not found: {target}")
        return payload["data"]

    def _fetch_tweets(self, client: httpx.Client, user_id: str, limit: int) -> dict[str, Any]:
        response = client.get(
            f"/users/{user_id}/tweets",
            params={
                "max_results": min(max(limit, 5), 100),
                "tweet.fields": "created_at,attachments,author_id,entities",
                "expansions": "attachments.media_keys,author_id",
                "media.fields": "duration_ms,height,media_key,preview_image_url,type,url,variants,width",
            },
        )
        response.raise_for_status()
        return response.json()


def _select_media_url(media: dict[str, Any]) -> str | None:
    if media.get("url"):
        return media["url"]
    variants = media.get("variants") or []
    candidates: list[tuple[int, str]] = []
    for variant in variants:
        url = variant.get("url")
        content_type = variant.get("content_type", "")
        if not url or "mp4" not in content_type:
            continue
        candidates.append((int(variant.get("bit_rate") or 0), url))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]
