import json
from pathlib import Path
import threading
from datetime import datetime, timezone

from camera.rtsp import CameraProbeResult, RtspProbe, build_rtsp_url
from config import AgentConfig, CameraConfig, load_config, save_config
from local.server import serve_local_agent
from local.state import StateStore


def test_builds_tapo_rtsp_url_with_encoded_credentials() -> None:
    url = build_rtsp_url("192.168.0.104", 554, "/stream1", "Toppadel", "p@ssword")
    assert url == "rtsp://Toppadel:p%40ssword@192.168.0.104:554/stream1"


def test_probe_reports_online_only_after_decoding_a_frame(monkeypatch) -> None:
    calls = []

    class Result:
        returncode = 0
        stdout = b""

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return Result()

    monkeypatch.setattr("camera.rtsp.shutil.which", lambda _name: "/usr/bin/ffmpeg")
    probe = RtspProbe(runner=runner)
    probe_result = probe.check("rtsp://camera.local:554/stream1")
    assert isinstance(probe_result, CameraProbeResult)
    assert probe_result.status == "online"
    assert "rtsp://camera.local:554/stream1" in calls[0][0]
    assert calls[0][0][-4:] == ["1", "-f", "null", "-"]


def test_local_config_is_persisted_with_camera_secret(tmp_path: Path) -> None:
    path = tmp_path / "agent.json"
    config = AgentConfig(
        cloud_api_url="https://api.courtvision.test",
        agent_token="agent-token",
        storage_dir=str(tmp_path / "media"),
        camera=CameraConfig(camera_id="camera-01", host="192.168.0.104", username="Toppadel", password="camera-secret"),
    )
    save_config(path, config)
    loaded = load_config(path)
    assert loaded.camera.rtsp_url.endswith("192.168.0.104:554/stream1")
    assert loaded.camera.password == "camera-secret"


def test_state_store_round_trips_status(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "agent-state.json")
    store.mark_probe("online", "ok")
    assert StateStore(tmp_path / "agent-state.json").snapshot()["camera_status"] == "online"


def test_local_status_endpoint_never_exposes_camera_password(tmp_path: Path) -> None:
    config = AgentConfig(storage_dir=str(tmp_path / "media"), camera=CameraConfig(camera_id="camera-01", host="192.168.0.104", password="secret"))
    from runtime.agent import LocalAgentRuntime

    runtime = LocalAgentRuntime(tmp_path / "agent.json", config)
    server = serve_local_agent(runtime, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        import urllib.request

        with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/v1/status") as response:
            body = json.load(response)
        assert "password" not in json.dumps(body)
    finally:
        server.shutdown()
        server.server_close()


def test_runtime_uses_recent_detector_frame_as_camera_health(tmp_path: Path) -> None:
    config = AgentConfig(
        storage_dir=str(tmp_path / "media"),
        camera=CameraConfig(camera_id="camera-01", host="192.168.0.104"),
    )
    from runtime.agent import LocalAgentRuntime

    runtime = LocalAgentRuntime(tmp_path / "agent.json", config)

    class UnexpectedProbe:
        def check(self, _url):
            raise AssertionError("A live detector frame must avoid a third RTSP connection")

    runtime.probe = UnexpectedProbe()
    runtime.state.update(gesture_last_frame_at=datetime.now(timezone.utc).isoformat())

    assert runtime.check_camera()["state"]["camera_status"] == "online"
