from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
from urllib.parse import quote, urlsplit, urlunsplit


@dataclass(frozen=True)
class CameraProbeResult:
    status: str
    detail: str
    observed_at: datetime
    codecs: tuple[str, ...] = ()


def build_rtsp_url(host: str, port: int, path: str, username: str = "", password: str = "") -> str:
    clean_host = host.strip()
    clean_path = path.strip() or "/stream1"
    if not clean_path.startswith("/"):
        clean_path = f"/{clean_path}"
    hostname = f"[{clean_host}]" if ":" in clean_host and not clean_host.startswith("[") else clean_host
    credentials = ""
    if username:
        credentials = f"{quote(username, safe='')}:{quote(password, safe='')}@"
    return f"rtsp://{credentials}{hostname}:{int(port)}{clean_path}"


def inject_credentials(url: str, username: str = "", password: str = "") -> str:
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "rtsp" or not parsed.hostname:
        raise ValueError("La ruta de la cámara debe ser una URL RTSP válida")
    if parsed.username or not username:
        return url
    hostname = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    netloc = f"{quote(username, safe='')}:{quote(password, safe='')}@{hostname}"
    if parsed.port:
        netloc += f":{parsed.port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


class RtspProbe:
    def __init__(self, timeout_seconds: float = 8, runner=subprocess.run) -> None:
        self.timeout_seconds = timeout_seconds
        self.runner = runner

    def check(self, url: str) -> CameraProbeResult:
        observed_at = datetime.now(timezone.utc)
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return CameraProbeResult("degraded", "ffmpeg no está instalado en el equipo local", observed_at)
        try:
            result = self.runner(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel", "error",
                    "-rtsp_transport", "tcp",
                    "-timeout", str(int(self.timeout_seconds * 1_000_000)),
                    "-i",
                    url,
                    "-map", "0:v:0",
                    "-frames:v", "1",
                    "-f", "null",
                    "-",
                ],
                capture_output=True,
                timeout=self.timeout_seconds + 2,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return CameraProbeResult("offline", "No se pudo alcanzar la cámara desde este equipo", observed_at)
        if result.returncode != 0:
            return CameraProbeResult("offline", "La cámara no está entregando imagen", observed_at)
        return CameraProbeResult("online", "Cámara accesible desde vivoo", observed_at, ("video",))


def probe_camera(host: str, port: int, path: str, username: str = "", password: str = "") -> CameraProbeResult:
    return RtspProbe().check(build_rtsp_url(host, port, path, username, password))
