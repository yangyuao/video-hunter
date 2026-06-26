from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from pprint import pprint

from video_hunter import db
from video_hunter.audit.x_originality import audit_x_author_timelines, audit_x_bookmarks
from video_hunter.importers.x_bookmarks import import_x_bookmarks
from video_hunter.importers.x_follow_graph import import_x_follow_graph
from video_hunter.importers.x_graph import sync_x_graph_from_files
from video_hunter.ingest import crawl_all, crawl_source, rebuild_indexes
from video_hunter.x_media import resolve_and_download_x_videos


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m video_hunter")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db")
    subparsers.add_parser("list-sources")

    add_source = subparsers.add_parser("add-source")
    add_source.add_argument("--platform", required=True, choices=["webpage", "direct", "x", "91porn"])
    add_source.add_argument("--target-type", required=True)
    add_source.add_argument("--target-value", required=True)
    add_source.add_argument("--crawl-interval-seconds", type=int, default=3600)

    crawl = subparsers.add_parser("crawl-once")
    crawl.add_argument("--source-id", type=int)
    crawl.add_argument("--limit", type=int, default=50)

    import_bookmarks = subparsers.add_parser("import-x-bookmarks")
    import_bookmarks.add_argument("--input", required=True, help="JSON file exported from Chrome X bookmarks")

    audit_bookmarks = subparsers.add_parser("audit-x-bookmarks")
    audit_bookmarks.add_argument("--input", default="data/x_bookmarks_export.json")
    audit_bookmarks.add_argument("--output-dir", default="data/reports")

    audit_timelines = subparsers.add_parser("audit-x-author-timelines")
    audit_timelines.add_argument("--input", default="data/reports/x_author_recent_timelines.json")
    audit_timelines.add_argument("--output-dir", default="data/reports")

    sync_graph = subparsers.add_parser("sync-x-graph")
    sync_graph.add_argument("--bookmarks", default="data/x_bookmarks_export.json")
    sync_graph.add_argument("--timelines", default="data/reports/x_author_recent_timelines.json")
    sync_graph.add_argument("--originality", default="data/reports/x_author_recent_originality_report.json")

    import_follow_graph = subparsers.add_parser("import-x-follow-graph")
    import_follow_graph.add_argument("--input", default="data/reports/x_follow_graph.json")

    download_x = subparsers.add_parser("download-x-videos")
    download_x.add_argument("--limit", type=int, default=10)
    download_x.add_argument("--no-download", action="store_true", help="Resolve MP4 URLs without downloading files")

    subparsers.add_parser("rebuild")

    args = parser.parse_args()
    db.init_db()

    if args.command == "init-db":
        print("Database initialized.")
    elif args.command == "list-sources":
        pprint(db.list_sources())
    elif args.command == "add-source":
        source_id = db.add_source(
            args.platform,
            args.target_type,
            args.target_value,
            args.crawl_interval_seconds,
        )
        print(f"Source #{source_id} saved.")
    elif args.command == "crawl-once":
        if args.source_id:
            pprint(asdict(crawl_source(args.source_id, limit=args.limit)))
        else:
            pprint([asdict(item) for item in crawl_all(limit=args.limit)])
    elif args.command == "import-x-bookmarks":
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload = payload.get("items", [])
        pprint(asdict(import_x_bookmarks(payload)))
    elif args.command == "audit-x-bookmarks":
        paths = audit_x_bookmarks(Path(args.input), Path(args.output_dir))
        pprint({key: str(value) for key, value in asdict(paths).items()})
    elif args.command == "audit-x-author-timelines":
        paths = audit_x_author_timelines(Path(args.input), Path(args.output_dir))
        pprint({key: str(value) for key, value in asdict(paths).items()})
    elif args.command == "sync-x-graph":
        result = sync_x_graph_from_files(
            bookmarks_path=Path(args.bookmarks),
            timelines_path=Path(args.timelines),
            originality_path=Path(args.originality),
        )
        pprint(asdict(result))
    elif args.command == "import-x-follow-graph":
        result = import_x_follow_graph(Path(args.input))
        pprint(asdict(result))
    elif args.command == "download-x-videos":
        result = resolve_and_download_x_videos(limit=args.limit, download=not args.no_download)
        pprint(asdict(result))
    elif args.command == "rebuild":
        pprint(rebuild_indexes())


if __name__ == "__main__":
    main()
