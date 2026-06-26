from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional at runtime
    load_dotenv = None


if load_dotenv is not None:
    load_dotenv()


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    db_path: Path
    storage_dir: Path
    max_download_mb: int
    download_media: bool
    x_bearer_token: str | None
    proxy_url: str | None
    proxy_auto_detect: bool

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            db_path=Path(os.getenv("VIDEO_HUNTER_DB", "data/video_hunter.sqlite3")),
            storage_dir=Path(os.getenv("VIDEO_HUNTER_STORAGE", "data/storage")),
            max_download_mb=int(os.getenv("VIDEO_HUNTER_MAX_DOWNLOAD_MB", "300")),
            download_media=_bool_env("VIDEO_HUNTER_DOWNLOAD_MEDIA", True),
            x_bearer_token=os.getenv("X_BEARER_TOKEN") or None,
            proxy_url=os.getenv("VIDEO_HUNTER_PROXY") or None,
            proxy_auto_detect=_bool_env("VIDEO_HUNTER_PROXY_AUTO_DETECT", True),
        )


settings = Settings.from_env()


def outbound_proxy_url() -> str | None:
    if settings.proxy_url:
        return settings.proxy_url
    if not settings.proxy_auto_detect:
        return None
    return detect_local_proxy()


def detect_local_proxy() -> str | None:
    for port in configured_clash_ports() + [7897, 7890, 7899, 7898, 1087, 1080]:
        if _port_open("127.0.0.1", port):
            return f"http://127.0.0.1:{port}"
    return None


def configured_clash_ports() -> list[int]:
    app_support = Path.home() / "Library/Application Support/io.github.clash-verge-rev.clash-verge-rev"
    candidates = [
        app_support / "config.yaml",
        app_support / "clash-verge.yaml",
        app_support / "clash-verge-check.yaml",
    ]
    ports: list[int] = []
    for path in candidates:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line != line.lstrip():
                continue
            stripped = line.strip()
            for key in ("mixed-port", "port"):
                prefix = f"{key}:"
                if stripped.startswith(prefix):
                    value = stripped[len(prefix) :].strip().strip("'\"")
                    if value.isdigit():
                        ports.append(int(value))
    return list(dict.fromkeys(ports))


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        try:
            sock.connect((host, port))
            return True
        except OSError:
            return False
