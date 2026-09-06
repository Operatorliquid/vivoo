from pathlib import Path

import runtime.supervisor as supervisor_module
from config import AgentConfig


class FakeRuntime:
    def __init__(self, config_path, config):
        self.config_path = config_path
        self.config = config
        self.stopped = False

    def run_background(self):
        return None

    def sync_cloud_config(self):
        return None

    def check_camera(self):
        return {"status": "online"}

    def safe_status(self):
        return {
            "camera": {"camera_id": self.config.camera.camera_id, "host": self.config.camera.host},
            "recording": {"active": False},
        }

    def update_config(self, _changes):
        return self.safe_status()

    def stop(self):
        self.stopped = True


def test_supervisor_keeps_each_camera_runtime_isolated(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(supervisor_module, "LocalAgentRuntime", FakeRuntime)
    supervisor = supervisor_module.MultiCameraSupervisor(
        tmp_path / "agent.json",
        AgentConfig(cloud_api_url="https://tveo.test/api", storage_dir=str(tmp_path / "media")),
    )

    supervisor.configure({"camera": {"camera_id": "camera-one", "host": "192.168.0.101"}, "agent_token": "one"})
    supervisor.configure({"camera": {"camera_id": "camera-two", "host": "192.168.0.102"}, "agent_token": "two"})

    assert supervisor.camera_ids() == ["camera-one", "camera-two"]
    assert supervisor.runtime("camera-one").config.camera.host == "192.168.0.101"
    assert supervisor.runtime("camera-two").config.camera.host == "192.168.0.102"
    assert supervisor.runtime("camera-one").config.storage_dir != supervisor.runtime("camera-two").config.storage_dir

    removed = supervisor.runtime("camera-one")
    supervisor.remove("camera-one")
    assert removed.stopped is True
    assert supervisor.camera_ids() == ["camera-two"]
