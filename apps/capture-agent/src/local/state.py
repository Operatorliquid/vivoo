from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import threading


@dataclass
class AgentState:
    camera_status: str = "offline"
    camera_detail: str = "Todavía no se verificó la cámara"
    last_probe_at: str | None = None
    last_heartbeat_at: str | None = None
    active_session_id: str | None = None
    recording_session_id: str | None = None
    recording: bool = False
    queued_events: int = 0
    last_error: str | None = None
    last_uploaded_recording: str | None = None
    gesture_detector_status: str = "idle"
    gesture_detector_detail: str = "Iniciá la grabación para detectar gestos"
    last_gesture_at: str | None = None
    last_gesture_confidence: float | None = None
    gesture_last_frame_at: str | None = None
    gesture_people_count: int = 0
    gesture_tracked_people: int = 0
    gesture_arms_raised: bool = False
    gesture_pose_confidence: float = 0.0
    gesture_inference_fps: float = 0.0
    gesture_inference_ms: float = 0.0


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self.state = self._load()

    def _load(self) -> AgentState:
        if not self.path.exists():
            return AgentState()
        try:
            return AgentState(**json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, TypeError, ValueError):
            return AgentState(last_error="El estado local estaba dañado y fue reiniciado")

    def update(self, **changes: object) -> AgentState:
        with self._lock:
            for key, value in changes.items():
                if hasattr(self.state, key):
                    setattr(self.state, key, value)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(asdict(self.state), indent=2), encoding="utf-8")
            temporary.replace(self.path)
            return self.state

    def mark_probe(self, status: str, detail: str, error: str | None = None) -> AgentState:
        return self.update(
            camera_status=status,
            camera_detail=detail,
            last_probe_at=datetime.now(timezone.utc).isoformat(),
            last_error=error,
        )

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return asdict(self.state)
