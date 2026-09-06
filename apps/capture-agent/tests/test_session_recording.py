from datetime import datetime, timezone
from pathlib import Path
import threading
import time
from types import SimpleNamespace

from camera.recorder import LocalRecorder
from config import AgentConfig, CameraConfig
from runtime.agent import LocalAgentRuntime


class FakeProcess:
    def __init__(self) -> None:
        self.returncode = None
        self.terminated = False

    def poll(self):
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 0

    def wait(self, timeout=None):
        return self.returncode

    def kill(self) -> None:
        self.returncode = -9


def test_segmented_recorder_uses_bounded_ring_when_full_match_is_disabled(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def popen(command, **_kwargs):
        commands.append(command)
        return FakeProcess()

    recorder = LocalRecorder(tmp_path, popen=popen)
    recorder.start("rtsp://relay/court", "session-1", preserve_full_recording=False)

    assert recorder.running
    assert "-segment_time" in commands[0]
    assert commands[0][commands[0].index("-segment_wrap") + 1] == "12"
    assert commands[0][-1].endswith("segment-%06d.ts")
    assert recorder.stop() is None


def test_segmented_recorder_finalizes_full_match_when_enabled(tmp_path: Path) -> None:
    process = FakeProcess()

    def popen(_command, **_kwargs):
        return process

    commands: list[list[str]] = []

    def runner(command, **_kwargs):
        commands.append(command)

    recorder = LocalRecorder(tmp_path, popen=popen, runner=runner)
    recorder.start("rtsp://relay/court", "session-2", preserve_full_recording=True, rotation_degrees=180)
    assert "-segment_wrap" not in recorder.command

    session_dir = tmp_path / "recordings" / "session-session-2" / "segments"
    (session_dir / "segment-000000.ts").write_bytes(b"segment")
    output = recorder.stop()

    assert output == tmp_path / "recordings" / "session-session-2.mp4"
    assert "-display_rotation:v:0" in commands[0]
    assert commands[0][commands[0].index("-display_rotation:v:0") + 1] == "180"


def test_highlight_uses_timestamp_safe_concat_before_trimming(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def runner(command, **_kwargs):
        commands.append(command)
        if command[0] == "ffprobe":
            return SimpleNamespace(stdout="35.0")
        Path(command[-1]).write_bytes(b"video")
        return SimpleNamespace(stdout="")

    recorder = LocalRecorder(tmp_path, runner=runner)
    recorder.session_dir = tmp_path / "recordings" / "session-test" / "segments"
    recorder.session_dir.mkdir(parents=True)
    for index in range(8):
        (recorder.session_dir / f"segment-{index:06d}.ts").write_bytes(b"segment")

    output = recorder.export_recent_clip(tmp_path / "highlight.mp4", seconds=30)

    assert output.read_bytes() == b"video"
    assert commands[0][commands[0].index("-f") + 1] == "concat"
    assert commands[-1][commands[-1].index("-ss") + 1] == "5.000"


def test_runtime_starts_and_stops_recorder_from_cloud_session(tmp_path: Path) -> None:
    config = AgentConfig(
        storage_dir=str(tmp_path / "media"),
        camera=CameraConfig(camera_id="camera-01", host="camera.local", recording_enabled=False),
    )
    runtime = LocalAgentRuntime(tmp_path / "agent.json", config)

    calls: list[tuple[str, object]] = []

    class Recorder:
        running = False

        def start(self, _url, session_id, preserve_full_recording, rotation_degrees=0):
            calls.append(("start", session_id, preserve_full_recording, rotation_degrees))
            self.running = True

        def stop(self):
            calls.append(("stop", None))
            self.running = False
            return None

    runtime.recorder = Recorder()

    runtime.state.update(active_session_id="00000000-0000-0000-0000-000000000001")
    runtime.sync_recording()
    assert calls[0] == ("start", "00000000-0000-0000-0000-000000000001", True, 0)

    runtime.state.update(active_session_id=None)
    runtime.sync_recording()
    assert calls[-1] == ("stop", None)


def test_runtime_restarts_a_stalled_recorder_without_ending_the_match(tmp_path: Path) -> None:
    config = AgentConfig(
        relay_rtsp_url="rtsp://127.0.0.1:8554/tveo-camera",
        storage_dir=str(tmp_path / "media"),
        camera=CameraConfig(camera_id="camera-01", host="camera.local"),
    )
    runtime = LocalAgentRuntime(tmp_path / "agent.json", config)

    class Recorder:
        running = True
        healthy = False

        def restart(self, source):
            assert source == config.relay_rtsp_url
            self.healthy = True

    runtime.recorder = Recorder()
    session_id = "00000000-0000-0000-0000-000000000001"
    runtime.state.update(active_session_id=session_id, recording_session_id=session_id)

    runtime.sync_recording()

    assert runtime.recorder.healthy is True
    assert runtime.state.snapshot()["recording"] is True


def test_gesture_clip_processing_never_blocks_detector_thread(tmp_path: Path) -> None:
    config = AgentConfig(
        storage_dir=str(tmp_path / "media"),
        camera=CameraConfig(camera_id="camera-01", host="camera.local", detection_mode="arms_up"),
    )
    runtime = LocalAgentRuntime(tmp_path / "agent.json", config)
    runtime.state.update(active_session_id="00000000-0000-0000-0000-000000000001")
    processing_started = threading.Event()
    allow_finish = threading.Event()

    def slow_clip(_event):
        processing_started.set()
        allow_finish.wait(timeout=2)

    runtime._queue_event_with_media = slow_clip
    runtime.flush_outbox = lambda: None
    started_at = time.monotonic()

    runtime._handle_gesture(0.95, datetime.now(timezone.utc))

    assert time.monotonic() - started_at < 0.1
    assert processing_started.wait(timeout=1)
    allow_finish.set()
