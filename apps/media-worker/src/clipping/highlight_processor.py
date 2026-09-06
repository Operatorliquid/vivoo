from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ClipRequest:
    source_path: Path
    output_path: Path
    start_offset_seconds: int
    duration_seconds: int


def build_ffmpeg_command(request: ClipRequest) -> list[str]:
    if request.start_offset_seconds < 0:
        raise ValueError("start_offset_seconds cannot be negative")
    if request.duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        str(request.start_offset_seconds),
        "-i",
        str(request.source_path),
        "-t",
        str(request.duration_seconds),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-c",
        "copy",
        "-avoid_negative_ts",
        "make_zero",
        "-movflags",
        "+faststart",
        str(request.output_path),
    ]


def assemble_highlight(request: ClipRequest) -> Path:
    request.output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            build_ffmpeg_command(request),
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or str(error)).strip()[-1000:]
        raise RuntimeError(f"FFmpeg no pudo ensamblar el highlight: {detail}") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("FFmpeg excedió el tiempo máximo de procesamiento") from error
    return request.output_path
