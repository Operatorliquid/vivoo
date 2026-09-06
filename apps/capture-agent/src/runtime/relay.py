"""MediaMTX supervisor used by the packaged desktop runtime."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from config import relay_path_name


API_PATH_URL = "http://127.0.0.1:9997/v3/paths/get/courtvision"
API_ROOT = "http://127.0.0.1:9997/v3"
POLL_SECONDS = 2.0
STALL_SECONDS = 4.0
RESTART_DELAY_SECONDS = 2.0


class CameraNotConfigured(ValueError):
    pass


def camera_url(config_path: Path) -> str:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    camera = payload["camera"]
    host = str(camera["host"]).strip()
    if not host:
        raise CameraNotConfigured("La cámara todavía no está configurada")
    port = int(camera.get("rtsp_port", 554))
    stream_path = str(camera.get("stream_path", "/stream1")).strip() or "/stream1"
    if not stream_path.startswith("/"):
        stream_path = f"/{stream_path}"
    username = quote(str(camera.get("username", "")), safe="")
    password = quote(str(camera.get("password", "")), safe="")
    credentials = f"{username}:{password}@" if username else ""
    return f"rtsp://{credentials}{host}:{port}{stream_path}"


def camera_id(config_path: Path) -> str:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    return str(payload.get("camera", {}).get("camera_id", "")).strip()


def configured_camera_paths(base_config: Path) -> list[Path]:
    camera_configs = sorted((base_config.parent / "cameras").glob("camera-*.json"))
    return camera_configs or [base_config]


def desired_relay_sources(base_config: Path) -> dict[str, str]:
    desired: dict[str, str] = {}
    for path in configured_camera_paths(base_config):
        try:
            identifier = camera_id(path)
            if identifier:
                desired[relay_path_name(identifier)] = camera_url(path)
        except (OSError, KeyError, TypeError, CameraNotConfigured, json.JSONDecodeError):
            continue
    return desired


def _request_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(url, data=body, method=method, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=2) as response:
        value = json.load(response)
    return value if isinstance(value, dict) else {}


def sync_relay_sources(desired: dict[str, str], api_root: str = API_ROOT) -> None:
    """Configure isolated on-demand relay paths without restarting active readers."""
    configured = _request_json(f"{api_root}/config/paths/list")
    existing = {
        str(item.get("name")): str(item.get("source", ""))
        for item in configured.get("items", [])
        if isinstance(item, dict)
    }
    for name, source in desired.items():
        if existing.get(name) == source:
            continue
        encoded_name = quote(name, safe="")
        payload = {"source": source, "sourceOnDemand": True, "sourceOnDemandCloseAfter": "30s"}
        if name in existing:
            _request_json(f"{api_root}/config/paths/patch/{encoded_name}", method="PATCH", payload=payload)
        else:
            _request_json(f"{api_root}/config/paths/add/{encoded_name}", method="POST", payload=payload)


def relay_samples(api_root: str = API_ROOT) -> list[dict[str, Any]]:
    try:
        payload = _request_json(f"{api_root}/paths/list")
    except (OSError, HTTPError, URLError, ValueError):
        return []
    return [item for item in payload.get("items", []) if isinstance(item, dict)]


def relay_sample(api_url: str = API_PATH_URL) -> dict[str, Any] | None:
    try:
        with urlopen(api_url, timeout=1) as response:
            payload = json.load(response)
    except (OSError, URLError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def sample_has_reader(sample: dict[str, Any]) -> bool:
    readers = sample.get("readers", [])
    return bool(sample.get("ready")) and isinstance(readers, list) and bool(readers)


@dataclass
class StreamProgress:
    stall_seconds: float = STALL_SECONDS
    last_bytes: int | None = None
    last_progress_at: float = 0.0
    observed: bool = False

    def observe(self, sample: dict[str, Any] | None, now: float) -> bool:
        if sample is None or not sample_has_reader(sample):
            self.last_bytes = None
            self.last_progress_at = now
            self.observed = False
            return False
        current_bytes = int(sample.get("inboundBytes", sample.get("bytesReceived", 0)) or 0)
        if not self.observed or self.last_bytes is None or current_bytes != self.last_bytes:
            self.last_bytes = current_bytes
            self.last_progress_at = now
            self.observed = True
            return False
        return now - self.last_progress_at >= self.stall_seconds


def stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def supervise(agent_config: Path, binary: Path, relay_config: Path) -> int:
    stopping = False
    active_process: subprocess.Popen[bytes] | None = None

    def request_stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True
        if active_process is not None:
            stop_process(active_process)

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    while not stopping:
        desired = desired_relay_sources(agent_config)
        if not desired:
            time.sleep(POLL_SECONDS)
            continue
        environment = os.environ.copy()
        # Keep the legacy path valid while every runtime consumes its isolated
        # camera path. Credentials never leave this local child environment.
        environment["MTX_PATHS_COURTVISION_SOURCE"] = next(iter(desired.values()))
        active_process = subprocess.Popen([str(binary), str(relay_config)], env=environment)
        stream_progress: dict[str, StreamProgress] = {}
        applied: dict[str, str] = {}
        restart_reason = "MediaMTX finalizó"

        while not stopping and active_process.poll() is None:
            time.sleep(POLL_SECONDS)
            desired = desired_relay_sources(agent_config)
            if desired != applied:
                try:
                    sync_relay_sources(desired)
                    applied = desired
                except (OSError, HTTPError, URLError, ValueError):
                    # MediaMTX may still be opening its API; retry next cycle.
                    continue
            now = time.monotonic()
            stalled = False
            for sample in relay_samples():
                name = str(sample.get("name", ""))
                if name not in desired:
                    continue
                progress = stream_progress.setdefault(name, StreamProgress())
                if progress.observe(sample, now):
                    stalled = True
                    break
            if stalled:
                restart_reason = "Stream sin fotogramas"
                break

        if active_process.poll() is None:
            print(f"[watchdog] {restart_reason}; reiniciando relay", flush=True)
            stop_process(active_process)
        if stopping:
            return 0
        time.sleep(RESTART_DELAY_SECONDS)
    return 0
