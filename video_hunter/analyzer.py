from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from PIL import Image
except ImportError:  # pragma: no cover - optional if frame hashing is disabled
    Image = None


@dataclass(frozen=True)
class AnalysisResult:
    file_sha256: str
    duration_seconds: float | None
    width: int | None
    height: int | None
    frame_hashes: list[str]


def analyze_video(path: Path) -> AnalysisResult:
    probe = ffprobe(path)
    return AnalysisResult(
        file_sha256=sha256_file(path),
        duration_seconds=probe.get("duration_seconds"),
        width=probe.get("width"),
        height=probe.get("height"),
        frame_hashes=extract_frame_hashes(path, probe.get("duration_seconds")),
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ffprobe(path: Path) -> dict[str, Any]:
    if shutil.which("ffprobe") is None:
        return {}

    command = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        return {}

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {}

    duration = None
    if payload.get("format", {}).get("duration"):
        try:
            duration = float(payload["format"]["duration"])
        except (TypeError, ValueError):
            duration = None

    width = None
    height = None
    for stream in payload.get("streams", []):
        if stream.get("codec_type") == "video":
            width = stream.get("width")
            height = stream.get("height")
            break

    return {"duration_seconds": duration, "width": width, "height": height}


def extract_frame_hashes(path: Path, duration_seconds: float | None) -> list[str]:
    if Image is None or shutil.which("ffmpeg") is None:
        return []

    if duration_seconds and duration_seconds > 0:
        interval = max(duration_seconds / 6, 1)
    else:
        interval = 5

    with tempfile.TemporaryDirectory() as tmpdir:
        frame_pattern = str(Path(tmpdir) / "frame_%03d.jpg")
        command = [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-vf",
            f"fps=1/{interval}",
            "-frames:v",
            "6",
            frame_pattern,
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            return []
        frame_paths = sorted(Path(tmpdir).glob("frame_*.jpg"))
        return [average_hash(frame_path) for frame_path in frame_paths]


def average_hash(path: Path) -> str:
    if Image is None:
        return ""
    with Image.open(path) as image:
        grayscale = image.convert("L").resize((8, 8))
        pixels = list(grayscale.getdata())
    avg = sum(pixels) / len(pixels)
    bits = "".join("1" if pixel >= avg else "0" for pixel in pixels)
    return f"{int(bits, 2):016x}"
