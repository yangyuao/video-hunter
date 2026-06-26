# video-hunter

一个基础版的视频采集、分析、去重、聚类和最早来源追踪系统。

当前版本适合先跑通小规模白名单源：

- 指定网页：从 HTML、`og:video`、JSON-LD `VideoObject`、`<video>`、`.mp4/.webm/.m3u8` 链接里发现视频。
- 91porn：支持列表页/详情页发现 `view_video.php?viewkey=...`，并尝试提取详情页中的视频地址、缩略图和发布时间证据。
- 指定视频文件 URL：直接入库并尝试下载。
- 指定 X/Twitter 账号：通过官方 X API 拉取账号 posts 和媒体信息，需要 `X_BEARER_TOKEN`。
- X/Twitter Bookmarks：支持从已登录 Chrome 页面导出的 bookmarks JSON 导入含视频帖子。
- 基础分析：文件 SHA-256、`ffprobe` 元信息、关键帧 average hash。
- 基础去重：优先按文件哈希，其次按关键帧哈希相似度分组。
- 基础聚类：按标题/描述/正文关键词做轻量主题聚类。
- 最早来源：按每个内容组的 occurrence `published_at` 和系统 `first_seen_at` 排序，并保留证据。

## 快速开始

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python -m video_hunter init-db
uvicorn video_hunter.app:app --reload --port 8000
```

打开：

```text
http://127.0.0.1:8000
```

如果要分析视频尺寸、时长和关键帧，请安装 `ffmpeg`：

```bash
brew install ffmpeg
```

## 添加源

网页：

```bash
python -m video_hunter add-source --platform webpage --target-type page --target-value "https://example.com/videos"
python -m video_hunter crawl-once
```

直接视频 URL：

```bash
python -m video_hunter add-source --platform direct --target-type video_url --target-value "https://example.com/video.mp4"
python -m video_hunter crawl-once
```

X/Twitter 账号：

```bash
export X_BEARER_TOKEN="..."
python -m video_hunter add-source --platform x --target-type account --target-value "some_username"
python -m video_hunter crawl-once
```

91porn 页面或详情页：

```bash
python -m video_hunter add-source --platform 91porn --target-type page --target-value "https://91porn.com/"
python -m video_hunter crawl-once
```

如果你给的是单个详情页：

```bash
python -m video_hunter add-source --platform 91porn --target-type detail --target-value "https://91porn.com/view_video.php?viewkey=..."
python -m video_hunter crawl-once
```

X/Twitter Bookmarks 导入：

```bash
python -m video_hunter import-x-bookmarks --input data/x_bookmarks_export.json
```

X/Twitter Bookmarks 原帖作者和原创性信号审计：

```bash
python -m video_hunter audit-x-bookmarks --input data/x_bookmarks_export.json --output-dir data/reports
```

X/Twitter 作者近期 timeline 原创/转载信号审计：

```bash
python -m video_hunter audit-x-author-timelines --input data/reports/x_author_recent_timelines.json --output-dir data/reports
```

输出：

```text
data/reports/x_bookmark_authors.txt
data/reports/x_bookmark_originality_report.json
data/reports/x_bookmark_originality_report.md
data/reports/x_author_recent_originality_report.json
data/reports/x_author_recent_originality_report.md
```

也可以在首页用表单添加 source，然后点击抓取。

## 环境变量

复制 `.env.example` 后按需修改：

```bash
cp .env.example .env
```

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `VIDEO_HUNTER_DB` | `data/video_hunter.sqlite3` | SQLite 数据库路径 |
| `VIDEO_HUNTER_STORAGE` | `data/storage` | 下载视频和关键帧存储目录 |
| `VIDEO_HUNTER_MAX_DOWNLOAD_MB` | `300` | 单个视频最大下载大小 |
| `VIDEO_HUNTER_DOWNLOAD_MEDIA` | `true` | 是否下载可直接访问的视频文件 |
| `X_BEARER_TOKEN` | 空 | X API Bearer token |
| `VIDEO_HUNTER_PROXY` | 空 | 出站代理，例如 `http://127.0.0.1:7897` |
| `VIDEO_HUNTER_PROXY_AUTO_DETECT` | `true` | 自动探测 Clash Verge mixed/HTTP 端口 |

## 目录结构

```text
video_hunter/
  app.py                 # FastAPI API 和基础网页 UI
  __main__.py            # CLI
  db.py                  # SQLite schema 和数据访问
  ingest.py              # 采集、下载、分析、去重、聚类总管线
  analyzer.py            # ffprobe/ffmpeg/SHA-256/关键帧 hash
  dedup.py               # 内容组去重
  clustering.py          # 轻量主题聚类
  connectors/
    direct.py            # 直接视频 URL
    webpage.py           # 普通网页视频发现
    porn91.py            # 91porn 页面/详情页视频发现
    x_api.py             # X/Twitter 官方 API
  importers/
    x_bookmarks.py       # Chrome X bookmarks JSON 导入
```

## 需要你后续提供的信息

给我下面任意一种即可，我会继续把 connector 和规则补实：

- 具体视频网站 URL、频道页、作者页。
- X/Twitter 账号列表。
- 哪些视频文件 URL 必须抓取。
- 是否允许下载原视频，还是只保存元数据和关键帧。
- 你希望“最早发布”的置信度规则，比如是否优先信官方 API、网页发布时间、还是你自己的首次发现时间。

## 合规和限制

- 请只抓取你有权访问、保存和再展示的内容。
- X Bookmarks 通过 Chrome 页面导入时，系统只保存帖子 URL、作者、可见正文、发布时间、缩略图和“含视频”证据。X 页面里的实际视频地址通常是 `blob:` 流，不会自动变成可下载 MP4。
- 如果后续需要下载 X 原视频，建议走官方 X API；也可以单独接 `yt-dlp`，但需要你明确允许使用浏览器登录态/cookies。
