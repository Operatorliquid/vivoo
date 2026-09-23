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
    watermark_path: Path | None = None


@dataclass(frozen=True)
class WatermarkRequest:
    source_path: Path
    output_path: Path
    watermark_path: Path


WATERMARK_FILTER = (
    "[1:v]format=rgba,colorchannelmixer=aa=0.82[mark];"
    "[mark][0:v]scale2ref=w=trunc(main_w*0.18/2)*2:h=-1[wm][base];"
    "[base][wm]overlay=x=W-w-W*0.025:y=H-h-H*0.035:format=auto[v]"
)


def _watermark_args(watermark_path: Path, duration_seconds: int | None = None) -> list[str]:
    if not watermark_path.is_file():
        raise FileNotFoundError(f"Marca de agua no encontrada: {watermark_path}")
    args = [
        "-loop", "1", "-framerate", "1", "-i", str(watermark_path),
    ]
    if duration_seconds is not None:
        args.extend(["-t", str(duration_seconds)])
    args.extend([
        "-filter_complex", WATERMARK_FILTER,
        "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
        "-shortest", "-movflags", "+faststart",
    ])
    return args


def build_ffmpeg_command(request: ClipRequest) -> list[str]:
    if request.start_offset_seconds < 0:
        raise ValueError("start_offset_seconds cannot be negative")
    if request.duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        str(request.start_offset_seconds),
        "-i",
        str(request.source_path),
    ]
    if request.watermark_path is not None:
        command.extend(_watermark_args(request.watermark_path, request.duration_seconds))
    else:
        command.extend([
            "-t", str(request.duration_seconds),
            "-map", "0:v:0", "-map", "0:a?", "-c", "copy",
            "-avoid_negative_ts", "make_zero", "-movflags", "+faststart",
        ])
    command.append(str(request.output_path))
    return command


def build_watermark_command(request: WatermarkRequest) -> list[str]:
    if request.source_path.resolve() == request.output_path.resolve():
        raise ValueError("La salida marcada debe ser distinta del archivo fuente")
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(request.source_path),
        *_watermark_args(request.watermark_path),
        str(request.output_path),
    ]


def _media_duration(path: Path) -> float:
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return max(1.0, float(probe.stdout.strip()))


def _run(command: list[str], timeout: int, label: str) -> None:
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=timeout)
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or str(error)).strip()[-1000:]
        raise RuntimeError(f"FFmpeg no pudo procesar {label}: {detail}") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"FFmpeg excedió el tiempo máximo procesando {label}") from error


def assemble_highlight(request: ClipRequest) -> Path:
    request.output_path.parent.mkdir(parents=True, exist_ok=True)
    _run(build_ffmpeg_command(request), max(120, request.duration_seconds * 4), "el highlight")
    return request.output_path


def watermark_recording(request: WatermarkRequest) -> Path:
    request.output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = _media_duration(request.source_path)
    timeout = min(21_600, max(600, int(duration * 4) + 300))
    _run(build_watermark_command(request), timeout, "el partido completo")
    return request.output_path
