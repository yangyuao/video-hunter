from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from video_hunter import __version__, db
from video_hunter.config import outbound_proxy_url
from video_hunter.importers.x_bookmarks import import_x_bookmarks
from video_hunter.importers.x_follow_graph import import_x_follow_graph
from video_hunter.importers.x_graph import sync_x_graph_from_files
from video_hunter.ingest import crawl_all, crawl_source, rebuild_indexes
from video_hunter.x_media import resolve_and_download_x_videos
from video_hunter.ui import PREVIEW_HTML


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


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return PREVIEW_HTML


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


DASHBOARD_HTML = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>video-hunter</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f7f7f5;
      --panel: #ffffff;
      --text: #1f2933;
      --muted: #697386;
      --line: #d8dee4;
      --accent: #1665d8;
      --danger: #b42318;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
    }
    header {
      padding: 24px 32px 14px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }
    h1 { margin: 0; font-size: 24px; }
    main {
      display: grid;
      grid-template-columns: minmax(280px, 380px) 1fr;
      gap: 18px;
      padding: 18px 32px 32px;
    }
    section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }
    h2 {
      margin: 0 0 12px;
      font-size: 16px;
    }
    label {
      display: block;
      margin: 10px 0 5px;
      color: var(--muted);
      font-size: 13px;
    }
    input, select {
      width: 100%;
      padding: 9px 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      font-size: 14px;
      background: #fff;
    }
    button {
      border: 1px solid #0f56bd;
      border-radius: 6px;
      background: var(--accent);
      color: #fff;
      padding: 9px 12px;
      font-weight: 600;
      cursor: pointer;
    }
    button.secondary {
      border-color: var(--line);
      background: #fff;
      color: var(--text);
    }
    .actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 12px;
    }
    .stack { display: grid; gap: 18px; }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    th, td {
      padding: 9px 8px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }
    th { color: var(--muted); font-weight: 600; }
    code {
      background: #f0f3f6;
      border-radius: 4px;
      padding: 1px 4px;
      word-break: break-all;
    }
    .muted { color: var(--muted); }
    .error { color: var(--danger); white-space: pre-wrap; }
    .status {
      min-height: 22px;
      margin-top: 12px;
      color: var(--muted);
      font-size: 13px;
      white-space: pre-wrap;
    }
    @media (max-width: 900px) {
      main { grid-template-columns: 1fr; padding: 14px; }
      header { padding: 18px 14px 12px; }
    }
  </style>
</head>
<body>
  <header>
    <h1>video-hunter</h1>
    <div class="muted">白名单视频源采集、去重、聚类和最早来源追踪</div>
  </header>
  <main>
    <div class="stack">
      <section>
        <h2>添加采集源</h2>
        <label>平台</label>
        <select id="platform">
          <option value="webpage">webpage</option>
          <option value="direct">direct</option>
          <option value="x">x</option>
          <option value="91porn">91porn</option>
        </select>
        <label>类型</label>
        <input id="targetType" value="page" />
        <label>目标</label>
        <input id="targetValue" placeholder="网页 URL / 视频 URL / X username" />
        <div class="actions">
          <button onclick="addSource()">添加</button>
          <button class="secondary" onclick="crawlAll()">抓取全部</button>
          <button class="secondary" onclick="rebuild()">重建分组</button>
        </div>
        <div id="status" class="status"></div>
      </section>
      <section>
        <h2>采集源</h2>
        <div id="sources"></div>
      </section>
    </div>
    <div class="stack">
      <section>
        <h2>内容组与最早来源</h2>
        <div id="groups"></div>
      </section>
      <section>
        <h2>视频</h2>
        <div id="videos"></div>
      </section>
      <section>
        <h2>主题聚类</h2>
        <div id="clusters"></div>
      </section>
    </div>
  </main>
  <script>
    async function request(path, options) {
      const response = await fetch(path, options);
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text);
      }
      return response.json();
    }

    function setStatus(value, isError = false) {
      const node = document.getElementById("status");
      node.textContent = value;
      node.className = isError ? "status error" : "status";
    }

    async function addSource() {
      try {
        const payload = {
          platform: document.getElementById("platform").value,
          target_type: document.getElementById("targetType").value,
          target_value: document.getElementById("targetValue").value,
          crawl_interval_seconds: 3600,
          enabled: true
        };
        const result = await request("/api/sources", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(payload)
        });
        setStatus(`已添加 source #${result.id}`);
        await loadAll();
      } catch (error) {
        setStatus(error.message, true);
      }
    }

    async function crawlSource(id) {
      try {
        setStatus(`正在抓取 source #${id} ...`);
        const result = await request(`/api/crawl/${id}`, {method: "POST"});
        setStatus(JSON.stringify(result, null, 2));
        await loadAll();
      } catch (error) {
        setStatus(error.message, true);
      }
    }

    async function crawlAll() {
      try {
        setStatus("正在抓取全部 enabled sources ...");
        const result = await request("/api/crawl-all", {method: "POST"});
        setStatus(JSON.stringify(result, null, 2));
        await loadAll();
      } catch (error) {
        setStatus(error.message, true);
      }
    }

    async function rebuild() {
      const result = await request("/api/rebuild", {method: "POST"});
      setStatus(JSON.stringify(result, null, 2));
      await loadAll();
    }

    async function loadAll() {
      const [sources, groups, videos, clusters] = await Promise.all([
        request("/api/sources"),
        request("/api/groups"),
        request("/api/videos"),
        request("/api/clusters")
      ]);
      renderSources(sources);
      renderGroups(groups);
      renderVideos(videos);
      renderClusters(clusters);
    }

    function renderSources(items) {
      document.getElementById("sources").innerHTML = table(
        ["ID", "平台", "类型", "目标", "上次抓取", ""],
        items.map(item => [
          item.id,
          item.platform,
          item.target_type,
          code(item.target_value),
          item.last_crawled_at || "",
          `<button class="secondary" onclick="crawlSource(${item.id})">抓取</button>`
        ])
      );
    }

    function renderGroups(items) {
      document.getElementById("groups").innerHTML = table(
        ["ID", "重复数", "标题", "最早平台", "发布时间", "证据 URL"],
        items.map(item => [
          item.id,
          item.duplicate_count,
          escapeHtml(item.canonical_title || ""),
          item.earliest_platform || "",
          item.earliest_published_at || item.earliest_first_seen_at || "",
          link(item.earliest_source_url)
        ])
      );
    }

    function renderVideos(items) {
      document.getElementById("videos").innerHTML = table(
        ["ID", "状态", "标题", "平台", "发布时间", "主题"],
        items.map(item => [
          item.id,
          item.status,
          escapeHtml(item.title || ""),
          item.platform || "",
          item.published_at || "",
          escapeHtml(item.topic_label || "")
        ])
      );
    }

    function renderClusters(items) {
      document.getElementById("clusters").innerHTML = table(
        ["ID", "标签", "视频数", "关键词"],
        items.map(item => [
          item.id,
          escapeHtml(item.label || ""),
          item.video_count,
          escapeHtml((item.keywords || []).join(", "))
        ])
      );
    }

    function table(headers, rows) {
      if (!rows.length) return `<div class="muted">暂无数据</div>`;
      return `<table><thead><tr>${headers.map(h => `<th>${h}</th>`).join("")}</tr></thead><tbody>` +
        rows.map(row => `<tr>${row.map(cell => `<td>${cell ?? ""}</td>`).join("")}</tr>`).join("") +
        `</tbody></table>`;
    }

    function code(value) {
      return `<code>${escapeHtml(value || "")}</code>`;
    }

    function link(value) {
      if (!value) return "";
      const safe = escapeHtml(value);
      return `<a href="${safe}" target="_blank" rel="noreferrer">${safe}</a>`;
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    loadAll().catch(error => setStatus(error.message, true));
  </script>
</body>
</html>
"""
