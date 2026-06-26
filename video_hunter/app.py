from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from video_hunter import __version__, db
from video_hunter.config import outbound_proxy_url
from video_hunter.importers.x_bookmarks import import_x_bookmarks
from video_hunter.importers.x_follow_graph import import_x_follow_graph
from video_hunter.importers.x_graph import sync_x_graph_from_files
from video_hunter.ingest import crawl_all, crawl_source, rebuild_indexes
from video_hunter.x_media import resolve_and_download_x_videos

# Built frontend lives in frontend/dist (run `npm run build` there). In dev the
# Vite server (npm run dev) proxies /api here, so this static mount only matters
# for production-style single-port serving.
REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"

app = FastAPI(title="video-hunter", version=__version__)
db.init_db()


class SourceCreate(BaseModel):
    platform: str = Field(..., examples=["webpage", "direct", "x"])
    target_type: str = Field(..., examples=["page", "video_url", "account"])
    target_value: str
    crawl_interval_seconds: int = 3600
    enabled: bool = True


class IngestUrl(BaseModel):
    url: str


class XBookmarkImport(BaseModel):
    items: list[dict[str, Any]]


class XGraphSync(BaseModel):
    bookmarks_path: str = "data/x_bookmarks_export.json"
    timelines_path: str = "data/reports/x_author_recent_timelines.json"
    originality_path: str = "data/reports/x_author_recent_originality_report.json"


class XFollowGraphImport(BaseModel):
    input_path: str = "data/reports/x_follow_graph.json"


class LabelUpdate(BaseModel):
    label: str
    notes: Optional[str] = None


class XVideoDownload(BaseModel):
    limit: int = 10
    download: bool = True


@app.on_event("startup")
def startup() -> None:
    db.init_db()


@app.get("/")
def index():
    """Serve the built SPA. The UI is entirely in frontend/; this only returns
    a plain-text hint when the bundle hasn't been built yet (dev mode uses the
    Vite server directly)."""
    index_html = FRONTEND_DIST / "index.html"
    if index_html.exists():
        return FileResponse(index_html)
    return PlainTextResponse(
        "video-hunter API 正在运行，但前端尚未构建。\n"
        "开发：cd frontend && npm install && npm run dev（打开 Vite 提示的 :5173）\n"
        "生产：cd frontend && npm run build，之后刷新本页面。\n"
        "API 文档：/docs",
    )


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "version": __version__}


@app.get("/api/sources")
def api_sources() -> list[dict[str, Any]]:
    return db.list_sources()


@app.post("/api/sources")
def api_create_source(payload: SourceCreate) -> dict[str, Any]:
    source_id = db.add_source(
        payload.platform,
        payload.target_type,
        payload.target_value,
        payload.crawl_interval_seconds,
        payload.enabled,
    )
    return {"id": source_id}


@app.post("/api/ingest-url")
def api_ingest_url(payload: IngestUrl) -> dict[str, Any]:
    source_id = db.add_source("direct", "video_url", payload.url)
    result = crawl_source(source_id)
    return asdict(result)


@app.post("/api/import/x-bookmarks")
def api_import_x_bookmarks(payload: XBookmarkImport) -> dict[str, Any]:
    return asdict(import_x_bookmarks(payload.items))


@app.post("/api/import/x-graph")
def api_sync_x_graph(payload: XGraphSync) -> dict[str, Any]:
    result = sync_x_graph_from_files(
        bookmarks_path=Path(payload.bookmarks_path),
        timelines_path=Path(payload.timelines_path),
        originality_path=Path(payload.originality_path),
    )
    return asdict(result)


@app.post("/api/import/x-follow-graph")
def api_import_x_follow_graph(payload: XFollowGraphImport) -> dict[str, Any]:
    return asdict(import_x_follow_graph(Path(payload.input_path)))


@app.post("/api/x/download-videos")
def api_download_x_videos(payload: XVideoDownload) -> dict[str, Any]:
    result = resolve_and_download_x_videos(limit=max(1, min(payload.limit, 100)), download=payload.download)
    return asdict(result)


@app.post("/api/crawl/{source_id}")
def api_crawl_source(source_id: int) -> dict[str, Any]:
    try:
        result = crawl_source(source_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return asdict(result)


@app.post("/api/crawl-all")
def api_crawl_all() -> list[dict[str, Any]]:
    try:
        return [asdict(item) for item in crawl_all()]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/rebuild")
def api_rebuild() -> dict[str, int]:
    return rebuild_indexes()


@app.get("/api/videos")
def api_videos(limit: int = 500) -> list[dict[str, Any]]:
    return db.list_videos(limit=max(1, min(limit, 1000)))


@app.get("/api/videos/{video_id}")
def api_video_detail(video_id: int) -> dict[str, Any]:
    detail = db.get_video_detail(video_id)
    if not detail:
        raise HTTPException(status_code=404, detail="video not found")
    return detail


@app.post("/api/videos/{video_id}/label")
def api_update_video_label(video_id: int, payload: LabelUpdate) -> dict[str, Any]:
    detail = db.update_video_manual_label(video_id, payload.label, payload.notes)
    if not detail:
        raise HTTPException(status_code=404, detail="video not found")
    return detail


@app.get("/api/videos/{video_id}/stream")
def api_video_stream(video_id: int, request: Request):
    info = db.get_video_stream_info(video_id)
    if not info:
        raise HTTPException(status_code=404, detail="video not found")
    if info.get("status") == "safety_review":
        raise HTTPException(status_code=404, detail="playable media not available")

    storage_path = info.get("storage_path")
    if storage_path:
        path = Path(storage_path)
        if path.exists():
            return FileResponse(path, media_type="video/mp4")

    media_url = info.get("media_url")
    if not media_url or str(media_url).startswith("blob:"):
        raise HTTPException(status_code=404, detail="playable media not available")

    if info.get("platform") == "91porn" and info.get("source_url"):
        refreshed = _refresh_91porn_media_url(info["source_url"])
        if refreshed:
            media_url = refreshed

    return _proxy_video_stream(
        media_url=media_url,
        referer=info.get("source_url"),
        range_header=request.headers.get("range"),
    )


@app.get("/api/occurrences")
def api_occurrences() -> list[dict[str, Any]]:
    return db.list_occurrences()


@app.get("/api/groups")
def api_groups() -> list[dict[str, Any]]:
    return db.list_content_groups()


@app.get("/api/clusters")
def api_clusters() -> list[dict[str, Any]]:
    return db.list_topic_clusters()


@app.get("/api/x/graph")
def api_x_graph(
    hide_single: bool = True,
    types: Optional[str] = Query(default="following,reposted"),
) -> dict[str, Any]:
    relationship_types = [item.strip() for item in types.split(",") if item.strip()] if types else None
    return db.list_x_account_graph(
        relationship_types=relationship_types,
        hide_single_edge_nodes=hide_single,
    )


@app.get("/api/x/accounts/{handle}")
def api_x_account(handle: str) -> dict[str, Any]:
    account = db.get_x_account(handle)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    return account


@app.post("/api/x/accounts/{handle}/label")
def api_update_x_account_label(handle: str, payload: LabelUpdate) -> dict[str, Any]:
    try:
        return db.update_x_account_label(handle, payload.label, payload.notes)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _proxy_video_stream(media_url: str, referer: str | None, range_header: str | None):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
    }
    if referer:
        headers["Referer"] = referer
    if range_header:
        headers["Range"] = range_header

    client = httpx.Client(follow_redirects=True, timeout=60, proxy=outbound_proxy_url())
    try:
        request = client.build_request("GET", media_url, headers=headers)
        response = client.send(request, stream=True)
        if response.status_code == 416:
            response_headers = {}
            for key in ("content-length", "content-range", "accept-ranges"):
                if key in response.headers:
                    response_headers[key] = response.headers[key]
            response.close()
            client.close()
            return Response(status_code=416, headers=response_headers)
        response.raise_for_status()
    except Exception:
        client.close()
        raise

    response_headers = {}
    for key in ("content-length", "content-range", "accept-ranges"):
        if key in response.headers:
            response_headers[key] = response.headers[key]

    content_type = response.headers.get("content-type", "video/mp4")

    def iterator():
        try:
            for chunk in response.iter_bytes(1024 * 512):
                if chunk:
                    yield chunk
        finally:
            response.close()
            client.close()

    return StreamingResponse(
        iterator(),
        status_code=response.status_code,
        media_type=content_type,
        headers=response_headers,
    )


def _refresh_91porn_media_url(source_url: str) -> str | None:
    from video_hunter.connectors.porn91 import first_embedded_media_url, request_headers

    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=20,
            proxy=outbound_proxy_url(),
            headers=request_headers(source_url),
        ) as client:
            response = client.get(source_url)
            response.raise_for_status()
            return first_embedded_media_url(str(response.url), response.text)
    except Exception:
        return None


# Production: serve the built SPA. Mounted LAST so every /api/* route above
# takes precedence; StaticFiles(html=True) returns dist/index.html for "/".
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

