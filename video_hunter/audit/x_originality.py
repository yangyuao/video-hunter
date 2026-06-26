from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


NON_ORIGINAL_PATTERNS = [
    ("explicit_repost", re.compile(r"\b(repost|reposted|rt|retweet|via)\b", re.I)),
    ("credit_or_source", re.compile(r"\b(credit|credits|source|src|from)\b", re.I)),
    ("curation_language", re.compile(r"精选|投稿|搬运|转载|转自|转推|转发|来源|出处|原作者|侵删|合集|分享")),
    ("watermark_or_archive_language", re.compile(r"水印|存档|archive|clips?|collection|daily|hub", re.I)),
]

CURATION_ACCOUNT_PATTERN = re.compile(
    r"精选|投稿|搬运|转载|合集|archive|clips?|collection|daily|hub|bot|feed|精选",
    re.I,
)


@dataclass(frozen=True)
class AuditPaths:
    json_path: Path
    markdown_path: Path
    authors_path: Path


def audit_x_bookmarks(input_path: Path, output_dir: Path) -> AuditPaths:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    items = payload.get("items", payload if isinstance(payload, list) else [])
    output_dir.mkdir(parents=True, exist_ok=True)

    authors: dict[str, dict[str, Any]] = {}
    flagged_items: list[dict[str, Any]] = []

    for item in items:
        handle = normalize_handle(item.get("author_handle"), item.get("tweet_url"))
        if not handle:
            continue
        author = authors.setdefault(
            handle,
            {
                "handle": handle,
                "display_names": set(),
                "bookmarked_posts": 0,
                "bookmarked_video_posts": 0,
                "likely_non_original_posts": 0,
                "possible_non_original_posts": 0,
                "uncertain_posts": 0,
                "signals": defaultdict(int),
                "flagged_urls": [],
            },
        )
        if item.get("author_name"):
            author["display_names"].add(str(item["author_name"]))
        author["bookmarked_posts"] += 1
        if item.get("has_video"):
            author["bookmarked_video_posts"] += 1

        assessment = assess_item(item)
        for signal in assessment["signals"]:
            author["signals"][signal] += 1
        if assessment["status"] == "likely_non_original":
            author["likely_non_original_posts"] += 1
            author["flagged_urls"].append(item.get("tweet_url"))
            flagged_items.append({**assessment, "tweet_url": item.get("tweet_url"), "author": handle})
        elif assessment["status"] == "possible_non_original":
            author["possible_non_original_posts"] += 1
            author["flagged_urls"].append(item.get("tweet_url"))
            flagged_items.append({**assessment, "tweet_url": item.get("tweet_url"), "author": handle})
        else:
            author["uncertain_posts"] += 1

    normalized_authors = []
    for author in authors.values():
        bookmarked_posts = author["bookmarked_posts"]
        likely = author["likely_non_original_posts"]
        possible = author["possible_non_original_posts"]
        risk_score = likely * 2 + possible
        normalized_authors.append(
            {
                "handle": author["handle"],
                "display_names": sorted(author["display_names"]),
                "bookmarked_posts": bookmarked_posts,
                "bookmarked_video_posts": author["bookmarked_video_posts"],
                "likely_non_original_posts": likely,
                "possible_non_original_posts": possible,
                "uncertain_posts": author["uncertain_posts"],
                "risk_score": risk_score,
                "risk_level": risk_level(risk_score, bookmarked_posts),
                "signals": dict(sorted(author["signals"].items())),
                "flagged_urls": [url for url in author["flagged_urls"] if url][:10],
            }
        )

    normalized_authors.sort(
        key=lambda item: (
            item["risk_score"],
            item["bookmarked_video_posts"],
            item["bookmarked_posts"],
            item["handle"].lower(),
        ),
        reverse=True,
    )
    handles = sorted(authors.keys(), key=str.lower)
    report = {
        "input_path": str(input_path),
        "total_bookmarks": len(items),
        "video_bookmarks": sum(1 for item in items if item.get("has_video")),
        "unique_authors": len(handles),
        "likely_non_original_posts": sum(
            item["likely_non_original_posts"] for item in normalized_authors
        ),
        "possible_non_original_posts": sum(
            item["possible_non_original_posts"] for item in normalized_authors
        ),
        "method": {
            "type": "heuristic_signal_audit",
            "limits": [
                "This is not proof of true origin without media fingerprints and earliest-source evidence.",
                "X web bookmarks usually expose blob video URLs, so this pass audits visible post metadata only.",
            ],
        },
        "authors": normalized_authors,
        "flagged_items": flagged_items,
    }

    json_path = output_dir / "x_bookmark_originality_report.json"
    markdown_path = output_dir / "x_bookmark_originality_report.md"
    authors_path = output_dir / "x_bookmark_authors.txt"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    authors_path.write_text("\n".join(handles) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return AuditPaths(json_path=json_path, markdown_path=markdown_path, authors_path=authors_path)


def audit_x_author_timelines(input_path: Path, output_dir: Path) -> AuditPaths:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    author_rows = payload.get("authors", [])
    output_dir.mkdir(parents=True, exist_ok=True)

    report_authors: list[dict[str, Any]] = []
    flagged_items: list[dict[str, Any]] = []
    for author in author_rows:
        handle = author["handle"]
        posts = author.get("posts", [])
        own_posts = []
        declared_reposts = []
        likely = []
        possible = []
        for post in posts:
            if post.get("is_declared_repost"):
                declared_reposts.append(post)
                continue
            own_posts.append(post)
            assessment = assess_item(post)
            if assessment["status"] == "likely_non_original":
                likely.append({**assessment, "status_url": post.get("status_url")})
            elif assessment["status"] == "possible_non_original":
                possible.append({**assessment, "status_url": post.get("status_url")})

        for item in likely + possible:
            flagged_items.append({"author": handle, **item})

        report_authors.append(
            {
                "handle": handle,
                "profile_url": author.get("url"),
                "collected_posts": author.get("collected_posts", len(posts)),
                "error": author.get("error"),
                "own_posts": len(own_posts),
                "declared_reposts": len(declared_reposts),
                "video_posts": sum(1 for post in posts if post.get("has_video")),
                "likely_non_original_own_posts": len(likely),
                "possible_non_original_own_posts": len(possible),
                "flagged_urls": [item.get("status_url") for item in likely + possible if item.get("status_url")][:10],
                "declared_repost_urls": [
                    post.get("status_url") for post in declared_reposts if post.get("status_url")
                ][:10],
            }
        )

    report_authors.sort(
        key=lambda row: (
            row["likely_non_original_own_posts"] * 2
            + row["possible_non_original_own_posts"]
            + row["declared_reposts"],
            row["video_posts"],
            row["collected_posts"],
        ),
        reverse=True,
    )
    report = {
        "input_path": str(input_path),
        "scope": payload.get("scope", "recent_profile_timeline"),
        "max_posts_per_author": payload.get("max_posts_per_author"),
        "authors_checked": len(author_rows),
        "total_posts_checked": sum(row["collected_posts"] for row in report_authors),
        "total_own_posts": sum(row["own_posts"] for row in report_authors),
        "total_declared_reposts": sum(row["declared_reposts"] for row in report_authors),
        "total_video_posts": sum(row["video_posts"] for row in report_authors),
        "likely_non_original_own_posts": sum(
            row["likely_non_original_own_posts"] for row in report_authors
        ),
        "possible_non_original_own_posts": sum(
            row["possible_non_original_own_posts"] for row in report_authors
        ),
        "method": {
            "type": "recent_timeline_signal_audit",
            "limits": [
                "This checks recently visible profile timeline posts, not complete X history.",
                "Declared reposts are not treated as fake originals; they are separated from suspected undisclosed reposts.",
                "True originality still needs media fingerprints and earliest-source evidence.",
            ],
        },
        "authors": report_authors,
        "flagged_items": flagged_items,
    }

    json_path = output_dir / "x_author_recent_originality_report.json"
    markdown_path = output_dir / "x_author_recent_originality_report.md"
    authors_path = output_dir / "x_bookmark_authors.txt"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_timeline_markdown(report), encoding="utf-8")
    if not authors_path.exists():
        authors_path.write_text("\n".join(row["handle"] for row in report_authors) + "\n", encoding="utf-8")
    return AuditPaths(json_path=json_path, markdown_path=markdown_path, authors_path=authors_path)


def assess_item(item: dict[str, Any]) -> dict[str, Any]:
    text = str(item.get("text") or "")
    author_name = str(item.get("author_name") or "")
    author_handle = str(item.get("author_handle") or "")
    signals: list[str] = []

    for label, pattern in NON_ORIGINAL_PATTERNS:
        if pattern.search(text):
            signals.append(label)

    if CURATION_ACCOUNT_PATTERN.search(author_name) or CURATION_ACCOUNT_PATTERN.search(author_handle):
        signals.append("curation_account")

    media_url = item.get("media_url") or ""
    if isinstance(media_url, str) and media_url.startswith("blob:"):
        signals.append("x_blob_video_no_direct_fingerprint")

    scoring_signals = [signal for signal in signals if signal != "x_blob_video_no_direct_fingerprint"]
    if len(scoring_signals) >= 2:
        status = "likely_non_original"
    elif len(scoring_signals) == 1:
        status = "possible_non_original"
    else:
        status = "uncertain"

    return {
        "status": status,
        "signals": signals,
        "published_at": item.get("published_at"),
        "has_video": bool(item.get("has_video")),
    }


def normalize_handle(value: Any, tweet_url: Any = None) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip().lstrip("@")
    if isinstance(tweet_url, str):
        match = re.search(r"x\.com/([^/?#]+)/status/\d+", tweet_url)
        if match:
            return match.group(1)
    return None


def risk_level(score: int, total: int) -> str:
    if score >= 4 or (total > 0 and score / total >= 1.5):
        return "high"
    if score >= 2:
        return "medium"
    if score >= 1:
        return "low"
    return "unknown"


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# X Bookmark Originality Audit",
        "",
        f"- Total bookmarks: {report['total_bookmarks']}",
        f"- Video bookmarks: {report['video_bookmarks']}",
        f"- Unique original posters: {report['unique_authors']}",
        f"- Likely non-original bookmarked posts: {report['likely_non_original_posts']}",
        f"- Possible non-original bookmarked posts: {report['possible_non_original_posts']}",
        "",
        "This report is a signal audit, not proof. Strong proof needs video/audio fingerprints and earliest-source evidence.",
        "",
        "## Authors",
        "",
        "| Handle | Bookmarks | Video bookmarks | Likely | Possible | Risk | Signals |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for author in report["authors"]:
        signals = ", ".join(f"{key}:{value}" for key, value in author["signals"].items())
        lines.append(
            "| "
            + " | ".join(
                [
                    f"@{author['handle']}",
                    str(author["bookmarked_posts"]),
                    str(author["bookmarked_video_posts"]),
                    str(author["likely_non_original_posts"]),
                    str(author["possible_non_original_posts"]),
                    author["risk_level"],
                    signals or "",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Flagged URLs",
            "",
        ]
    )
    for item in report["flagged_items"]:
        lines.append(
            f"- @{item['author']} {item['status']} {item.get('tweet_url') or ''} "
            f"signals={','.join(item['signals'])}"
        )
    lines.append("")
    return "\n".join(lines)


def render_timeline_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# X Author Recent Timeline Originality Audit",
        "",
        f"- Authors checked: {report['authors_checked']}",
        f"- Recent posts checked: {report['total_posts_checked']}",
        f"- Own posts: {report['total_own_posts']}",
        f"- Declared reposts: {report['total_declared_reposts']}",
        f"- Video posts: {report['total_video_posts']}",
        f"- Likely non-original own posts: {report['likely_non_original_own_posts']}",
        f"- Possible non-original own posts: {report['possible_non_original_own_posts']}",
        "",
        "Declared reposts are separated from suspected undisclosed non-original posts. This is a recent timeline signal audit, not full-history proof.",
        "",
        "| Handle | Checked | Own | Declared reposts | Videos | Likely own non-original | Possible own non-original |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for author in report["authors"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"@{author['handle']}",
                    str(author["collected_posts"]),
                    str(author["own_posts"]),
                    str(author["declared_reposts"]),
                    str(author["video_posts"]),
                    str(author["likely_non_original_own_posts"]),
                    str(author["possible_non_original_own_posts"]),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Flagged Own Posts", ""])
    for item in report["flagged_items"]:
        lines.append(
            f"- @{item['author']} {item['status']} {item.get('status_url') or ''} "
            f"signals={','.join(item['signals'])}"
        )
    lines.append("")
    return "\n".join(lines)
