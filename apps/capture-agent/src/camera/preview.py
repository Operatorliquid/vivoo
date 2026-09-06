from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterator
from threading import Lock


_preview_lock = Lock()
_active_preview: subprocess.Popen[bytes] | None = None


def _start_preview(command: list[str]) -> subprocess.Popen[bytes]:
    """Keep a single camera preview connection alive at a time.

    Tapo cameras expose only a small number of concurrent RTSP sessions. Replacing
    the low-frequency thumbnail before opening live view reserves those sessions
    for recording and pose inference.
    """
    global _active_preview
    with _preview_lock:
        previous = _active_preview
        _active_preview = None
        if previous is not None and previous.poll() is None:
            previous.terminate()
            try:
                previous.wait(timeout=2)
            except subprocess.TimeoutExpired:
                previous.kill()
                previous.wait(timeout=2)
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        _active_preview = process
        return process


def stream_mjpeg(rtsp_url: str, fps: int, rotation_degrees: int = 0) -> Iterator[bytes]:
    if fps not in (1, 15):
        raise ValueError("Velocidad de preview inválida")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise OSError("ffmpeg no está instalado en el equipo local")
    rotations = {
        0: "",
        90: "transpose=1,",
        180: "hflip,vflip,",
        270: "transpose=2,",
    }
    if rotation_degrees not in rotations:
        raise ValueError("La rotación debe ser 0, 90, 180 o 270 grados")
    process = _start_preview(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-rtsp_transport", "tcp", "-timeout", "8000000", "-i", rtsp_url, "-an", "-vf", f"fps={fps},{rotations[rotation_degrees]}scale=iw:ih", "-q:v", "5", "-f", "mpjpeg", "-boundary_tag", "ffmpeg", "pipe:1"],
    )
    try:
        if process.stdout is None:
            return
        while True:
            chunk = process.stdout.read(64 * 1024)
            if not chunk:
                return
            yield chunk
    finally:
        global _active_preview
        with _preview_lock:
            if _active_preview is process:
                _active_preview = None
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
