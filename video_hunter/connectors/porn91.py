from __future__ import annotations

import re
import urllib.parse
from typing import Iterable
from urllib.parse import parse_qs, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from video_hunter.config import outbound_proxy_url
from video_hunter.connectors.base import CandidateVideo, Connector, CrawlContext, SourceTarget
from video_hunter.connectors.webpage import extract_video_candidates


BASE_URL = "https://91porn.com/"
DETAIL_RE = re.compile(r"""(?:https?://[^"'<>\s]+)?/?view_video\.php\?[^"'<>\s]+""", re.I)


class Porn91Connector(Connector):
    def crawl(self, source: SourceTarget, context: CrawlContext) -> list[CandidateVideo]:
        target_url = normalize_91porn_url(source.target_value)
        target_type = source.target_type.strip().lower()
        headers = request_headers(target_url)

        proxy_url = outbound_proxy_url()
        with httpx.Client(follow_redirects=True, timeout=30, headers=headers, proxy=proxy_url) as client:
            if target_type in {"video", "detail", "url"} or is_detail_url(target_url):
                return [self._crawl_detail(client, target_url, context)]

            response = client.get(target_url)
            response.raise_for_status()
            detail_urls = extract_detail_urls(str(response.url), response.text)

            candidates: list[CandidateVideo] = []
            for detail_url in detail_urls[: context.limit]:
                try:
                    candidates.append(self._crawl_detail(client, detail_url, context))
                except httpx.HTTPError:
                    continue
            return candidates

    def _crawl_detail(
        self,
        client: httpx.Client,
        detail_url: str,
        context: CrawlContext,
    ) -> CandidateVideo:
        response = client.get(detail_url, headers=request_headers(detail_url))
        response.raise_for_status()
        page_url = str(response.url)
        html = response.text
        extracted = extract_video_candidates(
            page_url=page_url,
            html=html,
            platform="91porn",
            fetched_at=context.fetched_at,
            limit=5,
        )
        title = extract_title(html)
        published_at = extract_published_at(html)
        viewkey = extract_viewkey(page_url) or page_url

        for candidate in extracted:
            if candidate.media_url and not candidate.media_url.startswith("blob:"):
                return CandidateVideo(
                    platform="91porn",
                    source_url=page_url,
                    media_url=candidate.media_url,
                    platform_item_id=viewkey,
                    title=title or fallback_91_title(viewkey),
                    description=candidate.description,
                    published_at=candidate.published_at or published_at,
                    thumbnail_url=candidate.thumbnail_url,
                    evidence_type=f"91porn:{candidate.evidence_type}",
                    confidence_score=max(candidate.confidence_score, 0.75),
                    raw_metadata={
                        "viewkey": viewkey,
                        "detail_url": page_url,
                        "extractor": candidate.evidence_type,
                        "raw": candidate.raw_metadata,
                        "fetched_at": context.fetched_at,
                    },
                )

        media_url = first_embedded_media_url(page_url, html)
        return CandidateVideo(
            platform="91porn",
            source_url=page_url,
            media_url=media_url,
            platform_item_id=viewkey,
            title=title or fallback_91_title(viewkey),
            published_at=published_at,
            thumbnail_url=extract_thumbnail(html, page_url),
            evidence_type="91porn_detail_page",
            confidence_score=0.65 if media_url else 0.55,
            raw_metadata={
                "viewkey": viewkey,
                "detail_url": page_url,
                "has_media_url": bool(media_url),
                "fetched_at": context.fetched_at,
            },
        )


def normalize_91porn_url(value: str) -> str:
    raw = value.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    return urljoin(BASE_URL, raw.lstrip("/"))


def request_headers(referer: str | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.2",
        "Cookie": "language=cn_CN",
    }
    if referer:
        headers["Referer"] = referer
    return headers


def is_detail_url(url: str) -> bool:
    return "view_video.php" in urlparse(url).path


def extract_detail_urls(page_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    for href in _hrefs(soup):
        if "view_video.php" in href and "viewkey=" in href:
            urls.append(urljoin(page_url, href))
    for match in DETAIL_RE.findall(html):
        urls.append(urljoin(page_url, match))
    return list(dict.fromkeys(_strip_fragment(url) for url in urls))


def extract_title(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []
    for selector in (
        "meta[property='og:title']",
        "meta[name='twitter:title']",
    ):
        tag = soup.select_one(selector)
        if tag:
            text = tag.get("content")
            if text:
                candidates.append(_clean_91_title(text))

    for selector in (
        "#viewvideo-title",
        ".viewvideo-title",
        "h4.login_register_header",
        "title",
        "h1",
        "h2",
    ):
        tag = soup.select_one(selector)
        if tag:
            text = tag.get_text(" ", strip=True)
            if text:
                candidates.append(_clean_91_title(text))

    for value in candidates:
        if _contains_cjk(value) and _looks_like_video_title(value):
            return value
    return None


def fallback_91_title(viewkey: str | None) -> str:
    if viewkey and not viewkey.startswith(("http://", "https://")):
        return f"91视频 {viewkey}"
    return "91视频"


def extract_published_at(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["span", "div", "td", "p"]):
        text = tag.get_text(" ", strip=True)
        match = re.search(r"(20\d{2}[-/]\d{1,2}[-/]\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)", text)
        if match:
            return match.group(1).replace("/", "-")
    return None


def extract_thumbnail(html: str, page_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for selector in (
        "meta[property='og:image']",
        "meta[name='twitter:image']",
        "video[poster]",
        "img#thumbnail",
    ):
        tag = soup.select_one(selector)
        if not tag:
            continue
        value = tag.get("content") or tag.get("poster") or tag.get("src")
        if value:
            return urljoin(page_url, value)
    return None


def first_embedded_media_url(page_url: str, html: str) -> str | None:
    for encoded in re.findall(r"""strencode2\(["']([^"']+)["']\)""", html, flags=re.I):
        decoded = urllib.parse.unquote(encoded)
        match = re.search(
            r"""https?://[^"'<>\s]+\.(?:mp4|m4v|mov|webm|m3u8)(?:\?[^"'<>\s]+)?""",
            decoded,
            flags=re.I,
        )
        if match:
            return urljoin(page_url, match.group(0))

    html_without_comments = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    patterns = [
        r"""https?://[^"'<>\s]+\.(?:mp4|m4v|mov|webm|m3u8)(?:\?[^"'<>\s]+)?""",
        r"""(?:file|src)\s*[:=]\s*["']([^"']+\.(?:mp4|m4v|mov|webm|m3u8)(?:\?[^"']+)?)""",
    ]
    for pattern in patterns:
        match = re.search(pattern, html_without_comments, flags=re.I)
        if match:
            value = match.group(1) if match.groups() else match.group(0)
            return urljoin(page_url, value)
    return None


def extract_viewkey(url: str) -> str | None:
    parsed = urlparse(url)
    values = parse_qs(parsed.query).get("viewkey")
    if values:
        return values[0]
    return None


def _clean_91_title(value: str) -> str:
    return (
        value.replace("91Porn", "")
        .replace("91porn", "")
        .replace("- 91", "")
        .strip(" -|")
        .strip()
    )


def _contains_cjk(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", value))


def _looks_like_video_title(value: str) -> bool:
    if not value or len(value) > 180:
        return False
    blocked = (
        "视频信息",
        "此视频留言",
        "本月热播",
        "注册:",
        "粉丝:",
        "视频分享",
        "不要下载任何app",
        "全面打击诈骗",
        "约炮软件",
    )
    return not any(token in value for token in blocked)


def _hrefs(soup: BeautifulSoup) -> Iterable[str]:
    for tag in soup.select("a[href]"):
        href = tag.get("href")
        if href:
            yield href


def _strip_fragment(url: str) -> str:
    return url.split("#", 1)[0]
