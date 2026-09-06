from __future__ import annotations

import hashlib
import threading
from copy import deepcopy
from pathlib import Path

from config import AgentConfig, CameraConfig, camera_relay_url, save_config
from runtime.agent import LocalAgentRuntime


class MultiCameraSupervisor:
    """Owns one isolated capture runtime per paired camera on this computer."""

    def __init__(self, base_config_path: Path, base_config: AgentConfig) -> None:
        self.base_config_path = base_config_path
        self.base_config = base_config
        self.camera_root = base_config_path.parent / "cameras"
        self.camera_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._runtimes: dict[str, LocalAgentRuntime] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._load_existing()

    def _camera_path(self, camera_id: str) -> Path:
        digest = hashlib.sha256(camera_id.encode("utf-8")).hexdigest()[:20]
        return self.camera_root / f"camera-{digest}.json"

    def _start(self, config_path: Path, config: AgentConfig) -> LocalAgentRuntime:
        runtime = LocalAgentRuntime(config_path, config)
        camera_id = config.camera.camera_id
        thread = threading.Thread(target=runtime.run_background, name=f"camera-{camera_id[:8]}", daemon=True)
        self._runtimes[camera_id] = runtime
        self._threads[camera_id] = thread
        thread.start()
        return runtime

    def _load_existing(self) -> None:
        from config import load_config
        candidates = list(self.camera_root.glob("camera-*.json"))
        if self.base_config.camera.camera_id and not candidates:
            migrated = self._camera_path(self.base_config.camera.camera_id)
            migrated_config = deepcopy(self.base_config)
            migrated_config.relay_rtsp_url = camera_relay_url(
                self.base_config.relay_rtsp_url,
                migrated_config.camera.camera_id,
            )
            migrated_config.storage_dir = str(self.camera_root / migrated.stem / "media")
            save_config(migrated, migrated_config)
            candidates.append(migrated)
        for path in candidates:
            try:
                config = load_config(path)
                # Packaged builds resolve the bundled model on the base config.
                # Apply that absolute path to cameras created by older versions.
                if Path(self.base_config.pose_model).is_absolute() and config.pose_model != self.base_config.pose_model:
                    config.pose_model = self.base_config.pose_model
                    save_config(path, config)
                expected_relay = camera_relay_url(self.base_config.relay_rtsp_url, config.camera.camera_id)
                if config.relay_rtsp_url != expected_relay:
                    config.relay_rtsp_url = expected_relay
                    save_config(path, config)
                if config.camera.camera_id and config.camera.camera_id not in self._runtimes:
                    self._start(path, config)
            except (OSError, TypeError, ValueError):
                continue

    def camera_ids(self) -> list[str]:
        with self._lock:
            return sorted(self._runtimes)

    def runtime(self, camera_id: str | None) -> LocalAgentRuntime:
        with self._lock:
            if camera_id and camera_id in self._runtimes:
                return self._runtimes[camera_id]
            if not camera_id and len(self._runtimes) == 1:
                return next(iter(self._runtimes.values()))
        raise ValueError("Esta cámara todavía no está vinculada a esta PC")

    def safe_status(self, camera_id: str | None = None) -> dict[str, object]:
        with self._lock:
            if camera_id:
                selected = self._runtimes.get(camera_id)
                if selected is None:
                    raise ValueError("Esta cámara todavía no está vinculada a esta PC")
                runtimes = None
            elif len(self._runtimes) == 1:
                selected = next(iter(self._runtimes.values()))
                runtimes = None
            else:
                selected = None
                runtimes = list(self._runtimes.values())
        if selected is not None:
            return selected.safe_status()
        return {
            "supervisor": {"version": "0.7.0", "camera_count": len(runtimes or [])},
            "cameras": [item.safe_status() for item in runtimes or []],
        }

    def configure(self, changes: dict[str, object]) -> dict[str, object]:
        camera_changes = changes.get("camera")
        if not isinstance(camera_changes, dict) or not camera_changes.get("camera_id"):
            raise ValueError("Falta identificar la cámara")
        camera_id = str(camera_changes["camera_id"])
        with self._lock:
            existing = self._runtimes.get(camera_id)
            if existing:
                return existing.update_config(deepcopy(changes))
            config = deepcopy(self.base_config)
            config.camera = CameraConfig(camera_id=camera_id)
            config.agent_token = ""
            config.relay_rtsp_url = camera_relay_url(self.base_config.relay_rtsp_url, camera_id)
            path = self._camera_path(camera_id)
            config.storage_dir = str(self.camera_root / path.stem / "media")
            for key, value in changes.items():
                if key != "camera" and hasattr(config, key) and value is not None:
                    setattr(config, key, value)
            for key, value in camera_changes.items():
                if hasattr(config.camera, key) and value is not None:
                    setattr(config.camera, key, value)
            save_config(path, config)
            runtime = self._start(path, config)
        runtime.sync_cloud_config()
        runtime.check_camera()
        return runtime.safe_status()

    def remove(self, camera_id: str) -> None:
        with self._lock:
            runtime = self._runtimes.pop(camera_id, None)
            self._threads.pop(camera_id, None)
        if runtime:
            runtime.stop()
            runtime.config_path.unlink(missing_ok=True)

    def stop(self) -> None:
        with self._lock:
            runtimes = list(self._runtimes.values())
            self._runtimes.clear()
            self._threads.clear()
        for runtime in runtimes:
            runtime.stop()
