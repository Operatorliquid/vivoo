from datetime import datetime, timezone
from pathlib import Path

from client.api_client import AgentApiError
from config import AgentConfig, CameraConfig
from inference.events import NormalizedCaptureEvent
from local.outbox import EventOutbox
from runtime.agent import LocalAgentRuntime


def test_event_keeps_its_session_after_the_active_match_ends(tmp_path) -> None:
    outbox = EventOutbox(tmp_path / "outbox.sqlite3")
    event = NormalizedCaptureEvent(
        source_id="gesture-session-a",
        event_type="gesture",
        occurred_at=datetime.now(timezone.utc),
    )

    outbox.enqueue(event, session_id="2d841f14-1b4a-4eab-93ca-3cf5ef89c03d")

    pending = outbox.pending()
    assert pending[0]["payload"]["session_id"] == "2d841f14-1b4a-4eab-93ca-3cf5ef89c03d"


def test_recording_upload_survives_restart_and_tracks_attempts(tmp_path) -> None:
    database = tmp_path / "outbox.sqlite3"
    recording = tmp_path / "match.mp4"
    recording.write_bytes(b"video")
    outbox = EventOutbox(database)
    outbox.enqueue_media(
        "recording:session-a",
        "session-a",
        "recording",
        "video/mp4",
        recording,
    )
    outbox.mark_media_attempt("recording:session-a", "network unavailable")

    restored = EventOutbox(database)
    pending = restored.pending_media()
    assert pending[0]["session_id"] == "session-a"
    assert pending[0]["attempts"] == 1
    assert pending[0]["last_error"] == "network unavailable"

    restored.mark_media_sent("recording:session-a")
    assert restored.pending_media_count() == 0


def test_recording_upload_recovers_after_network_outage_and_agent_restart(tmp_path: Path) -> None:
    storage = tmp_path / "camera-media"
    source = storage / "recordings" / "session-offline.mp4"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"complete-match")
    config = AgentConfig(
        storage_dir=str(storage),
        camera=CameraConfig(camera_id="camera-01", field_id="field-01", host="camera.local"),
    )
    first = LocalAgentRuntime(tmp_path / "camera.json", config)
    first.outbox.enqueue_media(
        "recording:00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000001",
        "recording",
        "video/mp4",
        source,
    )

    class OfflineApi:
        def upload_resumable(self, *_args, **_kwargs):
            raise AgentApiError("internet unavailable")

    first.api = OfflineApi()
    assert first.flush_media_outbox() is False
    assert source.exists()
    assert first.outbox.pending_media_count() == 1

    class ReconnectedApi:
        def upload_resumable(self, *_args, **_kwargs):
            return {"storage_key": "sessions/session-offline/recording/checksum"}

    restarted = LocalAgentRuntime(tmp_path / "camera.json", config)
    restarted.api = ReconnectedApi()
    assert restarted.flush_media_outbox() is True
    assert restarted.outbox.pending_media_count() == 0
    assert not source.exists()
    assert restarted.state.snapshot()["last_uploaded_recording"] == "sessions/session-offline/recording/checksum"
