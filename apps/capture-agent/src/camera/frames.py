from __future__ import annotations

from collections.abc import Iterator
import shutil
import subprocess
import threading


def stream_bgr_frames(
    rtsp_url: str,
    stop_event: threading.Event,
    width: int = 640,
    height: int = 360,
    fps: int = 5,
    rotation_degrees: int = 0,
) -> Iterator[object]:
    """Decode RTSP with FFmpeg TCP transport and yield BGR NumPy frames."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise OSError("FFmpeg no está instalado en el equipo local")
    try:
        import numpy as np
    except ImportError as error:
        raise OSError("NumPy no está instalado para el detector de pose") from error

    rotations = {
        0: "",
        90: "transpose=1,",
        180: "hflip,vflip,",
        270: "transpose=2,",
    }
    if rotation_degrees not in rotations:
        raise ValueError("La rotación debe ser 0, 90, 180 o 270 grados")
    input_options = ["-rtsp_transport", "tcp", "-timeout", "8000000"] if rtsp_url.lower().startswith("rtsp://") else []
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        *input_options,
        "-i",
        rtsp_url,
        "-an",
        "-vf",
        f"fps={fps},{rotations[rotation_degrees]}scale={width}:{height}",
        "-pix_fmt",
        "bgr24",
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )
    frame_size = width * height * 3
    try:
        if process.stdout is None:
            raise OSError("FFmpeg no abrió la salida de video")
        while not stop_event.is_set():
            chunks = bytearray()
            while len(chunks) < frame_size and not stop_event.is_set():
                part = process.stdout.read(frame_size - len(chunks))
                if not part:
                    break
                chunks.extend(part)
            if len(chunks) != frame_size:
                break
            yield np.frombuffer(chunks, dtype=np.uint8).reshape((height, width, 3))
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
        if process.stdout:
            process.stdout.close()
