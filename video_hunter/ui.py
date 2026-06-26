from __future__ import annotations


PREVIEW_HTML = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>video-hunter</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f7f7;
      --surface: #ffffff;
      --surface-soft: #eef3f2;
      --text: #18212a;
      --muted: #65727f;
      --line: #d8e0df;
      --line-strong: #b6c4c2;
      --green: #167862;
      --blue: #2467a3;
      --amber: #a56818;
      --red: #af3f4a;
      --ink: #1d2935;
      --shadow: 0 18px 44px rgba(18, 34, 47, 0.12);
    }
    * { box-sizing: border-box; }
    html, body { min-height: 100%; overflow-x: hidden; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.4;
      overflow-x: hidden;
    }
    button, input, select, textarea { font: inherit; }
    a { color: var(--blue); text-decoration: none; }
    a:hover { text-decoration: underline; }
    .app {
      min-height: 100vh;
      display: grid;
      grid-template-columns: 292px minmax(0, 1fr) 360px;
      grid-template-rows: 66px minmax(0, 1fr);
    }
    .topbar {
      grid-column: 1 / -1;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      padding: 0 22px;
      background: var(--surface);
      border-bottom: 1px solid var(--line);
    }
    .brand {
      min-width: 0;
      display: flex;
      align-items: baseline;
      gap: 12px;
    }
    h1 {
      margin: 0;
      font-size: 18px;
      letter-spacing: 0;
      white-space: nowrap;
    }
    .brand span {
      color: var(--muted);
      font-size: 13px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .stats {
      display: flex;
      gap: 8px;
      justify-content: flex-end;
      flex-wrap: wrap;
    }
    .stat {
      min-width: 76px;
      padding: 6px 10px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #fbfcfc;
    }
    .stat strong {
      display: block;
      font-size: 14px;
    }
    .stat span {
      display: block;
      color: var(--muted);
      font-size: 11px;
    }
    .sidebar,
    .rightbar {
      min-height: 0;
      overflow: auto;
      background: var(--surface);
    }
    .sidebar {
      border-right: 1px solid var(--line);
      padding: 14px;
      display: grid;
      gap: 12px;
      align-content: start;
    }
    .rightbar {
      border-left: 1px solid var(--line);
      padding: 14px;
      display: grid;
      gap: 12px;
      align-content: start;
    }
    .main {
      min-width: 0;
      min-height: 0;
      overflow: hidden;
      padding: 16px;
    }
    .panel {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      padding: 13px;
    }
    .panel h2 {
      margin: 0 0 10px;
      font-size: 14px;
    }
    .segmented {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6px;
    }
    .tab,
    .btn {
      height: 34px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #fff;
      color: var(--text);
      padding: 0 10px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      cursor: pointer;
      text-decoration: none;
      white-space: nowrap;
    }
    .tab.active,
    .btn.primary {
      border-color: var(--green);
      background: var(--green);
      color: #fff;
    }
    .btn:hover,
    .tab:hover {
      border-color: var(--line-strong);
      text-decoration: none;
    }
    .control {
      display: grid;
      gap: 6px;
    }
    .control span {
      color: var(--muted);
      font-size: 12px;
    }
    select,
    input,
    textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #fff;
      color: var(--text);
      padding: 8px 9px;
    }
    textarea {
      min-height: 68px;
      resize: vertical;
    }
    .check {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
    }
    .check input {
      width: 16px;
      height: 16px;
    }
    .actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    .graph-shell,
    .video-shell {
      height: 100%;
      min-height: 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      box-shadow: var(--shadow);
      overflow: hidden;
    }
    .graph-shell {
      display: grid;
      grid-template-rows: 46px minmax(0, 1fr);
    }
    .canvasbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 0 14px;
      border-bottom: 1px solid var(--line);
      background: #fbfcfc;
    }
    .canvasbar strong { font-size: 13px; }
    .canvasbar span { color: var(--muted); font-size: 12px; }
    .graph-wrap {
      min-height: 0;
      position: relative;
      background:
        linear-gradient(rgba(29, 41, 53, .05) 1px, transparent 1px),
        linear-gradient(90deg, rgba(29, 41, 53, .05) 1px, transparent 1px);
      background-size: 28px 28px;
    }
    svg {
      display: block;
      width: 100%;
      height: 100%;
    }
    .edge {
      stroke: rgba(29, 41, 53, .24);
      stroke-width: 1.2;
    }
    .edge.reposted { stroke: rgba(36, 103, 163, .36); }
    .edge.following { stroke: rgba(22, 120, 98, .38); }
    .edge.bookmarked_author { stroke: rgba(165, 104, 24, .32); }
    .node circle {
      stroke: #fff;
      stroke-width: 2;
      filter: drop-shadow(0 5px 10px rgba(18, 34, 47, .18));
      cursor: pointer;
    }
    .node text {
      paint-order: stroke;
      stroke: rgba(255,255,255,.82);
      stroke-width: 3px;
      stroke-linejoin: round;
      fill: var(--ink);
      font-size: 11px;
      pointer-events: none;
    }
    .node.active circle {
      stroke: var(--ink);
      stroke-width: 3;
    }
    .legend {
      display: grid;
      gap: 7px;
      font-size: 12px;
      color: var(--muted);
    }
    .legend-row,
    .metric-row,
    .relation-row,
    .mini-video {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      min-width: 0;
    }
    .dot {
      width: 10px;
      height: 10px;
      border-radius: 999px;
      display: inline-block;
      margin-right: 7px;
    }
    .label-likely_original { background: var(--green); }
    .label-needs_review { background: var(--amber); }
    .label-likely_non_original { background: var(--red); }
    .label-reposter { background: var(--blue); }
    .label-unknown { background: #8b99a6; }
    .account-head {
      display: grid;
      gap: 8px;
    }
    .account-name {
      min-width: 0;
      font-size: 18px;
      font-weight: 700;
      overflow-wrap: anywhere;
    }
    .muted {
      color: var(--muted);
      font-size: 12px;
    }
    .pills {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      max-width: 100%;
      padding: 2px 8px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: #f8faf9;
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }
    .pill.green { color: var(--green); border-color: rgba(22,120,98,.28); background: #edf7f3; }
    .pill.amber { color: var(--amber); border-color: rgba(165,104,24,.28); background: #fff8ed; }
    .pill.red { color: var(--red); border-color: rgba(175,63,74,.28); background: #fff1f3; }
    .metric-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }
    .metric {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      min-width: 0;
      background: #fbfcfc;
    }
    .metric span {
      display: block;
      color: var(--muted);
      font-size: 11px;
      margin-bottom: 4px;
    }
    .metric strong {
      font-size: 14px;
      overflow-wrap: anywhere;
    }
    .relation-list,
    .mini-video-list,
    .video-list {
      display: grid;
      gap: 8px;
    }
    .relation-row,
    .mini-video,
    .video-item {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      padding: 9px;
      min-width: 0;
    }
    .relation-row a,
    .mini-video button {
      min-width: 0;
      overflow-wrap: anywhere;
      text-align: left;
    }
    .mini-video {
      align-items: flex-start;
    }
    .mini-video button {
      border: 0;
      background: transparent;
      padding: 0;
      color: var(--text);
      cursor: pointer;
    }
    .video-shell {
      display: grid;
      grid-template-columns: 360px minmax(0, 1fr);
      min-height: 0;
    }
    .video-pane {
      min-height: 0;
      overflow: auto;
      border-right: 1px solid var(--line);
      padding: 12px;
      display: grid;
      align-content: start;
      gap: 10px;
    }
    .video-list {
      min-height: 0;
    }
    .video-item {
      width: 100%;
      display: grid;
      grid-template-columns: 92px minmax(0, 1fr);
      gap: 10px;
      color: var(--text);
      cursor: pointer;
      text-align: left;
    }
    .video-item.active {
      border-color: var(--green);
      box-shadow: inset 3px 0 0 var(--green);
    }
    .thumb {
      width: 92px;
      aspect-ratio: 16 / 10;
      border-radius: 6px;
      background: linear-gradient(135deg, #dae3e0, #b8c8c4);
      overflow: hidden;
    }
    .thumb img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }
    .item-title {
      margin: 0;
      font-size: 13px;
      line-height: 1.28;
      display: -webkit-box;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 3;
      overflow: hidden;
      overflow-wrap: anywhere;
    }
    .player-pane {
      min-width: 0;
      min-height: 0;
      overflow: auto;
      padding: 14px;
      display: grid;
      gap: 12px;
      align-content: start;
    }
    .player-frame {
      background: #101417;
      border-radius: 8px;
      overflow: hidden;
      aspect-ratio: 16 / 9;
      display: grid;
      place-items: center;
    }
    video {
      width: 100%;
      height: 100%;
      background: #101417;
      display: block;
    }
    .poster {
      width: 100%;
      height: 100%;
      display: grid;
      place-items: center;
      position: relative;
      color: #fff;
      background: #101417;
    }
    .poster img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      opacity: .7;
    }
    .poster span {
      position: absolute;
      left: 16px;
      right: 16px;
      bottom: 16px;
      padding: 11px;
      border: 1px solid rgba(255,255,255,.18);
      border-radius: 8px;
      background: rgba(16,20,23,.84);
      font-size: 13px;
    }
    .player-title {
      margin: 0;
      font-size: 20px;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }
    .empty {
      padding: 14px;
      color: var(--muted);
      font-size: 13px;
    }
    .status {
      min-height: 18px;
      color: var(--muted);
      font-size: 12px;
      white-space: pre-wrap;
    }
    .status.error { color: var(--red); }
    .hidden { display: none !important; }
    @media (max-width: 1180px) {
      .app {
        grid-template-columns: 280px minmax(0, 1fr);
      }
      .rightbar {
        grid-column: 1 / -1;
        border-left: 0;
        border-top: 1px solid var(--line);
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .main { min-height: 620px; }
    }
    @media (max-width: 760px) {
      .app { display: block; }
      .topbar {
        width: 100vw;
        max-width: 100vw;
        min-height: 66px;
        padding: 12px;
        align-items: flex-start;
        flex-direction: column;
      }
      .brand,
      .stats {
        width: 100%;
      }
      .brand span {
        white-space: normal;
      }
      .stats {
        max-width: calc(100vw - 24px);
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .stat {
        min-width: 0;
      }
      .sidebar,
      .main,
      .rightbar,
      .panel {
        width: 100%;
        max-width: 100vw;
      }
      .sidebar,
      .rightbar {
        width: 100vw;
      }
      .panel {
        max-width: calc(100vw - 28px);
      }
      .legend-row {
        align-items: flex-start;
      }
      .legend-row span {
        min-width: 0;
      }
      .sidebar,
      .rightbar {
        border: 0;
      }
      .main {
        height: 620px;
        padding: 12px;
      }
      .video-shell {
        grid-template-columns: 1fr;
      }
      .video-pane {
        border-right: 0;
        border-bottom: 1px solid var(--line);
        max-height: 420px;
      }
      .rightbar {
        grid-template-columns: 1fr;
      }
      .metric-grid {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <div class="app">
    <header class="topbar">
      <div class="brand">
        <h1>video-hunter</h1>
        <span>X 书签作者图谱、视频整理和来源标记</span>
      </div>
      <div class="stats" id="stats"></div>
    </header>

    <aside class="sidebar">
      <section class="panel">
        <div class="segmented">
          <button id="graphTab" class="tab active" onclick="setMode('graph')">图谱</button>
          <button id="videoTab" class="tab" onclick="setMode('videos')">视频</button>
        </div>
      </section>

      <section class="panel" id="graphControls">
        <h2>图谱范围</h2>
        <div class="control">
          <span>关系</span>
          <select id="graphPreset" onchange="loadGraph()">
            <option value="follow-reposts">关注 + 转发</option>
            <option value="core-reposts">核心转发</option>
            <option value="all-reposts">全部转发</option>
            <option value="bookmarks">书签作者</option>
          </select>
        </div>
        <label class="check">
          <input id="hideSingle" type="checkbox" checked onchange="loadGraph()" />
          <span>隐藏单边节点</span>
        </label>
        <div class="actions">
          <button class="btn primary" onclick="syncGraph()">同步图谱</button>
          <button class="btn" onclick="loadGraph()">刷新</button>
        </div>
        <div class="status" id="graphStatus"></div>
      </section>

      <section class="panel" id="videoControls">
        <h2>视频筛选</h2>
        <div class="control">
          <span>搜索</span>
          <input id="videoSearch" placeholder="标题、作者、平台" />
        </div>
        <div class="control">
          <span>平台</span>
          <select id="platformFilter">
            <option value="all">全部平台</option>
          </select>
        </div>
        <div class="control">
          <span>播放状态</span>
          <select id="playableFilter">
            <option value="all">全部视频</option>
            <option value="playable">可播放</option>
            <option value="metadata">仅元数据</option>
          </select>
        </div>
        <div class="actions">
          <button class="btn primary" onclick="downloadXVideos(10)">下载 10 条 X 视频</button>
          <button class="btn" onclick="downloadXVideos(25)">下载 25 条</button>
        </div>
        <div class="status" id="downloadStatus"></div>
      </section>

      <section class="panel">
        <h2>标签</h2>
        <div class="legend">
          <div class="legend-row"><span><i class="dot label-likely_original"></i>疑似原创</span><span>原创信号较强</span></div>
          <div class="legend-row"><span><i class="dot label-needs_review"></i>待核验</span><span>有可疑信号</span></div>
          <div class="legend-row"><span><i class="dot label-likely_non_original"></i>疑似搬运</span><span>高风险</span></div>
          <div class="legend-row"><span><i class="dot label-reposter"></i>转发型</span><span>转发为主</span></div>
          <div class="legend-row"><span><i class="dot label-unknown"></i>未知</span><span>证据不足</span></div>
        </div>
      </section>
    </aside>

    <main class="main">
      <section id="graphView" class="graph-shell">
        <div class="canvasbar">
          <strong id="graphTitle">X 作者关系图</strong>
          <span id="graphMeta">加载中</span>
        </div>
        <div class="graph-wrap">
          <svg id="graphSvg" role="img" aria-label="X account graph"></svg>
        </div>
      </section>

      <section id="videoView" class="video-shell hidden">
        <div class="video-pane">
          <div class="video-list" id="videoList"></div>
        </div>
        <div class="player-pane">
          <div class="player-frame" id="playerFrame"></div>
          <h2 class="player-title" id="selectedTitle">暂无视频</h2>
          <div class="pills" id="selectedMeta"></div>
          <div class="actions" id="selectedActions"></div>
          <section class="panel">
            <h2>视频打标</h2>
            <div class="control">
              <span>原创状态</span>
              <select id="videoLabel">
                <option value="unknown">未知</option>
                <option value="likely_original">疑似原创</option>
                <option value="needs_review">待核验</option>
                <option value="likely_non_original">疑似搬运</option>
                <option value="repost">明确转载</option>
              </select>
            </div>
            <div class="control">
              <span>备注</span>
              <textarea id="videoNotes"></textarea>
            </div>
            <button class="btn primary" onclick="saveVideoLabel()">保存视频标签</button>
            <div class="status" id="videoStatus"></div>
          </section>
        </div>
      </section>
    </main>

    <aside class="rightbar">
      <section class="panel" id="accountPanel">
        <h2>作者</h2>
        <div id="accountDetail" class="empty">选择一个节点</div>
      </section>

      <section class="panel">
        <h2>作者打标</h2>
        <div class="control">
          <span>原创状态</span>
          <select id="accountLabel">
            <option value="unknown">未知</option>
            <option value="likely_original">疑似原创</option>
            <option value="needs_review">待核验</option>
            <option value="likely_non_original">疑似搬运</option>
            <option value="reposter">转发型</option>
          </select>
        </div>
        <div class="control">
          <span>备注</span>
          <textarea id="accountNotes"></textarea>
        </div>
        <button class="btn primary" onclick="saveAccountLabel()">保存作者标签</button>
        <div class="status" id="accountStatus"></div>
      </section>

      <section class="panel">
        <h2>关系</h2>
        <div id="relations" class="empty">暂无数据</div>
      </section>

      <section class="panel">
        <h2>作者视频</h2>
        <div id="accountVideos" class="mini-video-list"><div class="empty">暂无数据</div></div>
      </section>
    </aside>
  </div>

  <script>
    const state = {
      mode: "graph",
      graph: {nodes: [], edges: [], stats: {}},
      videos: [],
      selectedHandle: null,
      selectedAccount: null,
      selectedVideoId: null,
      selectedVideo: null,
    };

    const labelText = {
      likely_original: "疑似原创",
      needs_review: "待核验",
      likely_non_original: "疑似搬运",
      reposter: "转发型",
      repost: "明确转载",
      unknown: "未知",
    };

    const labelColor = {
      likely_original: "#167862",
      needs_review: "#a56818",
      likely_non_original: "#af3f4a",
      reposter: "#2467a3",
      repost: "#2467a3",
      unknown: "#8b99a6",
    };

    function videoDisplayTitle(video) {
      if (video.title) return video.title;
      if (video.platform === "91porn") return `91视频 #${video.id}`;
      return `Video #${video.id}`;
    }

    async function request(path, options) {
      const response = await fetch(path, options);
      if (!response.ok) {
        throw new Error(await response.text());
      }
      return response.json();
    }

    async function boot() {
      await Promise.all([loadVideos(), loadGraph()]);
      renderStats();
    }

    function setMode(mode) {
      state.mode = mode;
      document.getElementById("graphTab").classList.toggle("active", mode === "graph");
      document.getElementById("videoTab").classList.toggle("active", mode === "videos");
      document.getElementById("graphView").classList.toggle("hidden", mode !== "graph");
      document.getElementById("videoView").classList.toggle("hidden", mode !== "videos");
      document.getElementById("graphControls").classList.toggle("hidden", mode !== "graph");
      document.getElementById("videoControls").classList.toggle("hidden", mode !== "videos");
      if (mode === "graph") setTimeout(renderGraph, 0);
      if (mode === "videos") renderVideoList();
    }

    function graphQuery() {
      const preset = document.getElementById("graphPreset").value;
      const hide = document.getElementById("hideSingle").checked;
      if (preset === "all-reposts") return {types: "reposted", hide: false};
      if (preset === "follow-reposts") return {types: "following,reposted", hide};
      if (preset === "bookmarks") return {types: "bookmarked_author,reposted", hide: false};
      return {types: "reposted", hide};
    }

    async function loadGraph() {
      try {
        setStatus("graphStatus", "加载图谱");
        const query = graphQuery();
        state.graph = await request(`/api/x/graph?hide_single=${query.hide}&types=${encodeURIComponent(query.types)}`);
        setStatus("graphStatus", "");
        renderGraph();
        renderStats();
      } catch (error) {
        setStatus("graphStatus", error.message, true);
      }
    }

    async function syncGraph() {
      try {
        setStatus("graphStatus", "同步中");
        const result = await request("/api/import/x-graph", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({})
        });
        setStatus("graphStatus", `作者 ${result.bookmark_authors}，关系 ${result.repost_edges}，视频 ${result.imported_videos}`);
        await Promise.all([loadVideos(), loadGraph()]);
      } catch (error) {
        setStatus("graphStatus", error.message, true);
      }
    }

    function renderGraph() {
      const svg = document.getElementById("graphSvg");
      const bounds = svg.getBoundingClientRect();
      const width = Math.max(320, bounds.width || 900);
      const height = Math.max(420, bounds.height || 640);
      svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
      const nodes = state.graph.nodes.map(node => ({...node}));
      const nodeByHandle = new Map(nodes.map(node => [node.handle, node]));
      const edges = state.graph.edges.filter(edge => nodeByHandle.has(edge.source) && nodeByHandle.has(edge.target));
      document.getElementById("graphMeta").textContent =
        `${nodes.length} 个节点 / ${edges.length} 条边 / 隐藏 ${state.graph.stats.hidden_single_edge_nodes || 0}`;
      if (!nodes.length) {
        svg.innerHTML = `<text x="${width / 2}" y="${height / 2}" text-anchor="middle" fill="#65727f">暂无图谱数据</text>`;
        return;
      }
      layoutGraph(nodes, edges, width, height);
      const edgeSvg = edges.map(edge => {
        const s = nodeByHandle.get(edge.source);
        const t = nodeByHandle.get(edge.target);
        const sw = Math.min(5, 1 + Math.log2(edge.weight || 1));
        return `<line class="edge ${escapeAttr(edge.type)}" x1="${s.x}" y1="${s.y}" x2="${t.x}" y2="${t.y}" stroke-width="${sw.toFixed(2)}"></line>`;
      }).join("");
      const nodeSvg = nodes.map(node => {
        const active = node.handle === state.selectedHandle ? " active" : "";
        const label = node.effective_label || "unknown";
        const radius = Math.min(30, 10 + Math.sqrt((node.video_count || 0) + (node.degree || 0) + 1) * 2.6);
        const name = node.display_name || `@${node.handle}`;
        return `
          <g class="node${active}" transform="translate(${node.x},${node.y})" onclick="selectAccount('${escapeJs(node.handle)}')">
            <circle r="${radius.toFixed(1)}" fill="${labelColor[label] || labelColor.unknown}"></circle>
            <text y="${radius + 14}" text-anchor="middle">${escapeHtml(shortName(name, 18))}</text>
          </g>
        `;
      }).join("");
      svg.innerHTML = `<g>${edgeSvg}</g><g>${nodeSvg}</g>`;
    }

    function layoutGraph(nodes, edges, width, height) {
      const radius = Math.min(width, height) * 0.36;
      nodes.forEach((node, index) => {
        const angle = (Math.PI * 2 * index) / Math.max(1, nodes.length);
        node.x = width / 2 + Math.cos(angle) * radius * (0.68 + (index % 5) * 0.05);
        node.y = height / 2 + Math.sin(angle) * radius * (0.68 + (index % 7) * 0.04);
        node.vx = 0;
        node.vy = 0;
      });
      const byHandle = new Map(nodes.map(node => [node.handle, node]));
      for (let tick = 0; tick < 180; tick += 1) {
        for (let i = 0; i < nodes.length; i += 1) {
          for (let j = i + 1; j < nodes.length; j += 1) {
            const a = nodes[i];
            const b = nodes[j];
            let dx = a.x - b.x;
            let dy = a.y - b.y;
            let distance = Math.sqrt(dx * dx + dy * dy) || 1;
            const force = Math.min(2.8, 900 / (distance * distance));
            dx /= distance;
            dy /= distance;
            a.vx += dx * force;
            a.vy += dy * force;
            b.vx -= dx * force;
            b.vy -= dy * force;
          }
        }
        edges.forEach(edge => {
          const s = byHandle.get(edge.source);
          const t = byHandle.get(edge.target);
          if (!s || !t) return;
          const dx = t.x - s.x;
          const dy = t.y - s.y;
          const distance = Math.sqrt(dx * dx + dy * dy) || 1;
          const target = 120 - Math.min(48, (edge.weight || 1) * 3);
          const force = (distance - target) * 0.008;
          s.vx += (dx / distance) * force;
          s.vy += (dy / distance) * force;
          t.vx -= (dx / distance) * force;
          t.vy -= (dy / distance) * force;
        });
        nodes.forEach(node => {
          node.vx += (width / 2 - node.x) * 0.004;
          node.vy += (height / 2 - node.y) * 0.004;
          node.x += node.vx;
          node.y += node.vy;
          node.vx *= 0.72;
          node.vy *= 0.72;
          node.x = Math.max(54, Math.min(width - 54, node.x));
          node.y = Math.max(48, Math.min(height - 48, node.y));
        });
      }
    }

    async function selectAccount(handle) {
      try {
        state.selectedHandle = handle;
        renderGraph();
        state.selectedAccount = await request(`/api/x/accounts/${encodeURIComponent(handle)}`);
        renderAccount();
      } catch (error) {
        setStatus("accountStatus", error.message, true);
      }
    }

    function renderAccount() {
      const account = state.selectedAccount;
      if (!account) return;
      document.getElementById("accountLabel").value = account.manual_label || account.originality_label || "unknown";
      document.getElementById("accountNotes").value = account.notes || "";
      const label = account.effective_label || "unknown";
      document.getElementById("accountDetail").innerHTML = `
        <div class="account-head">
          <div class="account-name">${escapeHtml(account.display_name || `@${account.handle}`)}</div>
          <div class="muted">@${escapeHtml(account.handle)}</div>
          <div class="pills">
            <span class="pill ${pillClass(label)}">${escapeHtml(labelText[label] || label)}</span>
            <span class="pill">${account.video_count || 0} 视频</span>
            <span class="pill">${account.in_degree || 0} 入 / ${account.out_degree || 0} 出</span>
          </div>
          <div class="actions">
            <a class="btn primary" href="${escapeAttr(account.profile_url)}" target="_blank" rel="noreferrer">个人主页</a>
          </div>
          <div class="metric-grid">
            ${metric("书签", account.bookmarked_posts)}
            ${metric("书签视频", account.bookmarked_video_posts)}
            ${metric("近期贴文", account.timeline_posts)}
            ${metric("近期视频", account.timeline_video_posts)}
            ${metric("原创贴文", account.own_posts)}
            ${metric("声明转发", account.declared_reposts)}
            ${metric("疑似搬运", account.likely_non_original_posts)}
            ${metric("待核验", account.possible_non_original_posts)}
          </div>
        </div>
      `;
      renderRelations(account);
      renderAccountVideos(account);
    }

    function renderRelations(account) {
      const outgoing = (account.outgoing || []).slice(0, 10).map(row => relationRow("→", row));
      const incoming = (account.incoming || []).slice(0, 10).map(row => relationRow("←", row));
      const html = [...outgoing, ...incoming].join("");
      document.getElementById("relations").innerHTML = html || `<div class="empty">暂无关系</div>`;
    }

    function relationRow(prefix, row) {
      return `
        <div class="relation-row">
          <a href="${escapeAttr(row.profile_url || `https://x.com/${row.handle}`)}" target="_blank" rel="noreferrer">${prefix} @${escapeHtml(row.handle)}</a>
          <span class="pill">${escapeHtml(row.relationship_type)} ${row.weight || 1}</span>
        </div>
      `;
    }

    function renderAccountVideos(account) {
      const videos = account.videos || [];
      if (!videos.length) {
        document.getElementById("accountVideos").innerHTML = `<div class="empty">暂无视频</div>`;
        return;
      }
      document.getElementById("accountVideos").innerHTML = videos.slice(0, 18).map(video => `
        <div class="mini-video">
          <button onclick="openVideo(${video.id})">${escapeHtml(videoDisplayTitle(video))}</button>
          <span class="pill ${video.has_playback ? "green" : ""}">${video.has_playback ? "可播" : "元数据"}</span>
        </div>
      `).join("");
    }

    async function saveAccountLabel() {
      if (!state.selectedHandle) return;
      try {
        setStatus("accountStatus", "保存中");
        state.selectedAccount = await request(`/api/x/accounts/${encodeURIComponent(state.selectedHandle)}/label`, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            label: document.getElementById("accountLabel").value,
            notes: document.getElementById("accountNotes").value
          })
        });
        setStatus("accountStatus", "已保存");
        await loadGraph();
        renderAccount();
      } catch (error) {
        setStatus("accountStatus", error.message, true);
      }
    }

    async function loadVideos() {
      state.videos = await request("/api/videos?limit=500");
      renderPlatformOptions();
      renderVideoList();
      if (!state.selectedVideoId && state.videos.length) {
        const first = state.videos.find(video => video.has_playback) || state.videos[0];
        await selectVideo(first.id);
      }
      renderStats();
    }

    async function downloadXVideos(limit) {
      try {
        setMode("videos");
        setStatus("downloadStatus", `正在解析并下载 ${limit} 条 X 视频`);
        const result = await request("/api/x/download-videos", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({limit, download: true})
        });
        setStatus("downloadStatus", `完成：解析 ${result.resolved}，下载 ${result.downloaded}，失败 ${result.failed}`);
        await loadVideos();
      } catch (error) {
        setStatus("downloadStatus", error.message, true);
      }
    }

    function renderPlatformOptions() {
      const select = document.getElementById("platformFilter");
      const current = select.value;
      const platforms = Array.from(new Set(state.videos.map(video => video.platform).filter(Boolean))).sort();
      select.innerHTML = `<option value="all">全部平台</option>` + platforms.map(platform => `<option value="${escapeAttr(platform)}">${escapeHtml(platform)}</option>`).join("");
      select.value = platforms.includes(current) ? current : "all";
    }

    function filteredVideos() {
      const query = document.getElementById("videoSearch").value.trim().toLowerCase();
      const platform = document.getElementById("platformFilter").value;
      const playable = document.getElementById("playableFilter").value;
      return state.videos.filter(video => {
        if (platform !== "all" && video.platform !== platform) return false;
        if (playable === "playable" && !video.has_playback) return false;
        if (playable === "metadata" && video.has_playback) return false;
        if (!query) return true;
        return [video.title, video.author_name, video.author_handle, video.platform, video.topic_label]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(query);
      });
    }

    function renderVideoList() {
      const container = document.getElementById("videoList");
      const videos = filteredVideos();
      if (!videos.length) {
        container.innerHTML = `<div class="empty">没有匹配的视频</div>`;
        return;
      }
      container.innerHTML = videos.map(video => {
        const active = video.id === state.selectedVideoId ? " active" : "";
        const thumb = video.thumbnail_url ? `<img src="${escapeAttr(video.thumbnail_url)}" loading="lazy" />` : "";
        return `
          <button class="video-item${active}" onclick="selectVideo(${video.id})">
            <div class="thumb">${thumb}</div>
            <div>
              <h3 class="item-title">${escapeHtml(videoDisplayTitle(video))}</h3>
              <div class="pills">
                <span class="pill">${escapeHtml(video.platform || "")}</span>
                <span class="pill ${video.has_playback ? "green" : "amber"}">${video.has_playback ? "可播放" : "仅元数据"}</span>
                ${video.origin_label && video.origin_label !== "unknown" ? `<span class="pill ${pillClass(video.origin_label)}">${escapeHtml(labelText[video.origin_label] || video.origin_label)}</span>` : ""}
              </div>
            </div>
          </button>
        `;
      }).join("");
    }

    async function openVideo(id) {
      setMode("videos");
      await selectVideo(id);
    }

    async function selectVideo(id) {
      state.selectedVideoId = id;
      renderVideoList();
      state.selectedVideo = await request(`/api/videos/${id}`);
      renderSelectedVideo();
    }

    function renderSelectedVideo() {
      const video = state.selectedVideo;
      if (!video) return;
      document.getElementById("selectedTitle").textContent = videoDisplayTitle(video);
      document.getElementById("selectedMeta").innerHTML = [
        `<span class="pill">${escapeHtml(video.platform || "")}</span>`,
        `<span class="pill ${video.has_playback ? "green" : "amber"}">${video.has_playback ? "网页播放器" : "仅元数据"}</span>`,
        `<span class="pill">${escapeHtml(formatDate(video.display_time) || "未知时间")}</span>`,
        video.author_handle ? `<span class="pill">@${escapeHtml(video.author_handle)}</span>` : "",
        video.topic_label ? `<span class="pill">${escapeHtml(video.topic_label)}</span>` : ""
      ].join("");
      renderPlayer(video);
      renderVideoActions(video);
      document.getElementById("videoLabel").value = video.origin_label || "unknown";
      document.getElementById("videoNotes").value = video.origin_notes || "";
    }

    function renderPlayer(video) {
      const frame = document.getElementById("playerFrame");
      if (video.has_playback && video.playback_url) {
        const poster = video.thumbnail_url ? ` poster="${escapeAttr(video.thumbnail_url)}"` : "";
        frame.innerHTML = `<video controls preload="metadata"${poster}><source src="${escapeAttr(video.playback_url)}"></video>`;
        return;
      }
      const img = video.thumbnail_url ? `<img src="${escapeAttr(video.thumbnail_url)}" />` : "";
      frame.innerHTML = `<div class="poster">${img}<span>X 页面导出的条目没有稳定视频直链，先保存封面和来源。</span></div>`;
    }

    function renderVideoActions(video) {
      const actions = [];
      if (video.source_url) actions.push(`<a class="btn primary" href="${escapeAttr(video.source_url)}" target="_blank" rel="noreferrer">打开来源</a>`);
      if (video.author_profile_url) actions.push(`<a class="btn" href="${escapeAttr(video.author_profile_url)}" target="_blank" rel="noreferrer">作者主页</a>`);
      if (video.media_url) actions.push(`<a class="btn" href="${escapeAttr(video.media_url)}" target="_blank" rel="noreferrer">媒体直链</a>`);
      document.getElementById("selectedActions").innerHTML = actions.join("");
    }

    async function saveVideoLabel() {
      if (!state.selectedVideoId) return;
      try {
        setStatus("videoStatus", "保存中");
        state.selectedVideo = await request(`/api/videos/${state.selectedVideoId}/label`, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            label: document.getElementById("videoLabel").value,
            notes: document.getElementById("videoNotes").value
          })
        });
        setStatus("videoStatus", "已保存");
        await loadVideos();
        renderSelectedVideo();
      } catch (error) {
        setStatus("videoStatus", error.message, true);
      }
    }

    function renderStats() {
      const videos = state.videos.length;
      const playable = state.videos.filter(video => video.has_playback).length;
      const xVideos = state.videos.filter(video => video.platform === "x").length;
      const graphStats = state.graph.stats || {};
      document.getElementById("stats").innerHTML = [
        stat(graphStats.total_accounts || 0, "作者"),
        stat(graphStats.visible_edges || 0, "可见关系"),
        stat(videos, "视频"),
        stat(playable, "可播放"),
        stat(xVideos, "X")
      ].join("");
    }

    function stat(value, label) {
      return `<div class="stat"><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`;
    }

    function metric(label, value) {
      return `<div class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value ?? 0)}</strong></div>`;
    }

    function pillClass(label) {
      if (label === "likely_original") return "green";
      if (label === "needs_review") return "amber";
      if (label === "likely_non_original") return "red";
      return "";
    }

    function setStatus(id, value, isError = false) {
      const node = document.getElementById(id);
      node.textContent = value;
      node.className = isError ? "status error" : "status";
    }

    function formatDate(value) {
      if (!value) return "";
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return String(value).slice(0, 16);
      return date.toLocaleString("zh-CN", {hour12: false});
    }

    function shortName(value, max) {
      const text = String(value || "");
      return text.length > max ? `${text.slice(0, max - 1)}…` : text;
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function escapeAttr(value) {
      return escapeHtml(value).replaceAll("`", "&#096;");
    }

    function escapeJs(value) {
      return String(value ?? "").replaceAll("\\\\", "\\\\\\\\").replaceAll("'", "\\\\'");
    }

    document.getElementById("videoSearch").addEventListener("input", renderVideoList);
    document.getElementById("platformFilter").addEventListener("change", renderVideoList);
    document.getElementById("playableFilter").addEventListener("change", renderVideoList);
    window.addEventListener("resize", () => {
      if (state.mode === "graph") renderGraph();
    });

    boot().catch(error => {
      setStatus("graphStatus", error.message, true);
      setStatus("videoStatus", error.message, true);
    });
  </script>
</body>
</html>
"""
