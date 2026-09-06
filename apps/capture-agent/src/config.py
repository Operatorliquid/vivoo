from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import hashlib

from camera.rtsp import build_rtsp_url


@dataclass
class CameraConfig:
    camera_id: str = ""
    field_id: str = ""
    field_name: str = ""
    host: str = ""
    rtsp_port: int = 554
    username: str = ""
    password: str = ""
    stream_path: str = "/stream1"
    detection_mode: str = "arms_up"
    recording_enabled: bool = True

    @property
    def rtsp_url(self) -> str:
        return build_rtsp_url(self.host, self.rtsp_port, self.stream_path, self.username, self.password)


@dataclass
class AgentConfig:
    cloud_api_url: str = "http://127.0.0.1:8000"
    agent_token: str = ""
    storage_dir: str = "~/.courtvision/media"
    heartbeat_seconds: int = 30
    relay_rtsp_url: str = ""
    pose_model: str = "yolo26n-pose.pt"
    pose_device: str = "cpu"
    pose_image_size: int = 960
    pose_person_confidence: float = 0.30
    pose_keypoint_confidence: float = 0.35
    pose_rotation_degrees: int = 0
    pose_roi: list[float] = field(default_factory=lambda: [0.0, 0.0, 1.0, 1.0])
    pose_min_person_height_ratio: float = 0.06
    gesture_hold_seconds: float = 1.2
    gesture_cooldown_seconds: float = 0.0
    gesture_release_seconds: float = 0.75
    gesture_min_wrist_lift_ratio: float = 0.15
    gesture_min_local_motion: float = 0.10
    gesture_max_gap_seconds: float = 0.9
    camera: CameraConfig = field(default_factory=CameraConfig)

    @property
    def resolved_storage_dir(self) -> Path:
        return Path(os.path.expanduser(self.storage_dir)).resolve()

    @property
    def media_rtsp_url(self) -> str:
        """Local relay when configured, otherwise the camera itself."""
        return self.relay_rtsp_url.strip() or self.camera.rtsp_url


def relay_path_name(camera_id: str) -> str:
    """Return the stable, credential-free MediaMTX path for one camera."""
    digest = hashlib.sha256(camera_id.encode("utf-8")).hexdigest()[:20]
    return f"tveo-{digest}"


def camera_relay_url(base_url: str, camera_id: str) -> str:
    """Give every camera its own relay path while sharing one local server."""
    value = base_url.strip()
    if not value or not camera_id:
        return ""
    parsed = urlsplit(value)
    return urlunsplit((parsed.scheme, parsed.netloc, f"/{relay_path_name(camera_id)}", "", ""))


def load_config(path: Path) -> AgentConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    camera = CameraConfig(**payload.get("camera", {}))
    return AgentConfig(
        cloud_api_url=payload.get("cloud_api_url", "http://127.0.0.1:8000"),
        agent_token=payload.get("agent_token", ""),
        storage_dir=payload.get("storage_dir", "~/.courtvision/media"),
        heartbeat_seconds=int(payload.get("heartbeat_seconds", 30)),
        relay_rtsp_url=str(payload.get("relay_rtsp_url", "")),
        pose_model=str(payload.get("pose_model", "yolo26n-pose.pt")),
        pose_device=str(payload.get("pose_device", "cpu")),
        pose_image_size=int(payload.get("pose_image_size", 960)),
        pose_person_confidence=float(payload.get("pose_person_confidence", 0.30)),
        pose_keypoint_confidence=float(payload.get("pose_keypoint_confidence", 0.35)),
        pose_rotation_degrees=int(payload.get("pose_rotation_degrees", 0)),
        pose_roi=normalize_roi(payload.get("pose_roi", [0.0, 0.0, 1.0, 1.0])),
        pose_min_person_height_ratio=float(payload.get("pose_min_person_height_ratio", 0.06)),
        gesture_hold_seconds=float(payload.get("gesture_hold_seconds", 1.2)),
        # Migrate the original conservative defaults. Rearming now depends on a
        # clear down/up cycle, so a valid second gesture is no longer hidden for
        # 15 seconds and 0.75 s of neutral pose is enough to start another one.
        gesture_cooldown_seconds=(
            0.0
            if float(payload.get("gesture_cooldown_seconds", 15.0)) == 15.0
            else float(payload.get("gesture_cooldown_seconds", 0.0))
        ),
        gesture_release_seconds=(
            0.75
            if float(payload.get("gesture_release_seconds", 1.5)) == 1.5
            else float(payload.get("gesture_release_seconds", 0.75))
        ),
        gesture_min_wrist_lift_ratio=float(payload.get("gesture_min_wrist_lift_ratio", 0.15)),
        gesture_min_local_motion=float(payload.get("gesture_min_local_motion", 0.10)),
        gesture_max_gap_seconds=float(payload.get("gesture_max_gap_seconds", 0.9)),
        camera=camera,
    )


def normalize_roi(value: object) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("La zona del detector debe tener cuatro coordenadas")
    left, top, right, bottom = (max(0.0, min(1.0, float(item))) for item in value)
    if right - left < 0.1 or bottom - top < 0.1:
        raise ValueError("La zona del detector es demasiado pequeña")
    return [left, top, right, bottom]


def save_config(path: Path, config: AgentConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def write_example(
    path: Path,
    *,
    cloud_api_url: str | None = None,
    storage_dir: str | None = None,
    relay_rtsp_url: str | None = None,
) -> None:
    config = AgentConfig()
    if cloud_api_url:
        config.cloud_api_url = cloud_api_url.rstrip("/")
    if storage_dir:
        config.storage_dir = storage_dir
    if relay_rtsp_url:
        config.relay_rtsp_url = relay_rtsp_url
    save_config(path, config)
