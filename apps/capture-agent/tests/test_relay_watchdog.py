from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "run_mediamtx.py"
SPEC = spec_from_file_location("run_mediamtx", SCRIPT)
assert SPEC and SPEC.loader
run_mediamtx = module_from_spec(SPEC)
sys.modules[SPEC.name] = run_mediamtx
SPEC.loader.exec_module(run_mediamtx)


def test_relay_sample_requires_a_ready_path_with_a_reader() -> None:
    assert run_mediamtx.sample_has_reader({"ready": True, "readers": [{"id": "reader-1"}]}) is True
    assert run_mediamtx.sample_has_reader({"ready": True, "readers": []}) is False
    assert run_mediamtx.sample_has_reader({"ready": False, "readers": [{"id": "reader-1"}]}) is False


def test_stream_progress_detects_a_frozen_source_before_reader_timeout() -> None:
    progress = run_mediamtx.StreamProgress(stall_seconds=4)
    sample = {"ready": True, "readers": [{"id": "reader-1"}], "inboundBytes": 1200}
    assert progress.observe(sample, now=10) is False
    assert progress.observe(sample, now=13) is False
    assert progress.observe(sample, now=14) is True

    moving = {**sample, "inboundBytes": 2400}
    assert progress.observe(moving, now=15) is False
    assert progress.observe({"ready": True, "readers": []}, now=20) is False


def test_camera_url_encodes_credentials(tmp_path: Path) -> None:
    config = tmp_path / "agent.json"
    config.write_text(
        '{"camera":{"host":"192.168.1.8","rtsp_port":554,"stream_path":"stream1","username":"club","password":"p@ss"}}',
        encoding="utf-8",
    )
    assert run_mediamtx.camera_url(config) == "rtsp://club:p%40ss@192.168.1.8:554/stream1"


def test_camera_url_waits_until_camera_is_configured(tmp_path: Path) -> None:
    config = tmp_path / "agent.json"
    config.write_text('{"camera":{"host":""}}', encoding="utf-8")
    with pytest.raises(ValueError, match="todavía no está configurada"):
        run_mediamtx.camera_url(config)


def test_relay_discovers_an_isolated_source_for_every_camera(tmp_path: Path) -> None:
    base = tmp_path / "agent.json"
    base.write_text('{"camera":{"camera_id":"","host":""}}', encoding="utf-8")
    camera_root = tmp_path / "cameras"
    camera_root.mkdir()
    (camera_root / "camera-one.json").write_text(
        '{"camera":{"camera_id":"camera-one","host":"192.168.1.8","username":"club","password":"secret"}}',
        encoding="utf-8",
    )
    (camera_root / "camera-two.json").write_text(
        '{"camera":{"camera_id":"camera-two","host":"192.168.1.9"}}',
        encoding="utf-8",
    )

    desired = run_mediamtx.desired_relay_sources(base)

    assert len(desired) == 2
    assert len(set(desired)) == 2
    assert set(desired.values()) == {
        "rtsp://club:secret@192.168.1.8:554/stream1",
        "rtsp://192.168.1.9:554/stream1",
    }
