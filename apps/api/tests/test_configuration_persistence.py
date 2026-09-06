import json

from db.configuration import FileConfigurationPersistence


def test_local_configuration_survives_a_process_restart(tmp_path) -> None:
    persistence = FileConfigurationPersistence(str(tmp_path / "configuration.json"))
    persistence.initialize()
    persistence.save(
        "owner-01",
        {"id": "club-01", "name": "Club Norte", "city": "La Plata", "fields_count": 1},
        [{
            "id": "field-01", "name": "Cancha 01", "field_token": "field-01", "sport_code": "padel",
            "status": "active", "recording_enabled": True, "detection_mode": "arms_up",
            "qr_url": "/qr?field=field-01",
        }],
        [{
            "id": "camera-01", "field_id": "field-01", "name": "Tapo Norte", "host": "192.168.1.80",
            "rtsp_port": 554, "username": "operator", "password": "secret", "stream_path": "/stream1",
            "stream_url": "rtsp://192.168.1.80:554/stream1", "status": "ready", "last_seen": "recién cargada",
        }],
        {},
        {},
        [],
    )

    loaded = persistence.load("owner-01")

    assert loaded is not None
    assert loaded["cameras"][0]["host"] == "192.168.1.80"
    assert loaded["cameras"][0]["password"] == "secret"
    stored = json.loads((tmp_path / "configuration.json").read_text(encoding="utf-8"))
    assert stored["cameras"][0]["password"].startswith("encv1:")
    assert '"password": "secret"' not in (tmp_path / "configuration.json").read_text(encoding="utf-8")


def test_local_button_secret_is_encrypted_at_rest(tmp_path) -> None:
    path = tmp_path / "configuration.json"
    persistence = FileConfigurationPersistence(str(path))
    persistence.initialize()
    persistence.save(
        "owner-01",
        {"id": "club-01", "name": "Club Norte", "city": "", "fields_count": 0},
        [], [],
        {"field-01": {"device_id": "button-01", "label": "Botón", "status": "ready", "last_seen": "ahora"}},
        {"field-01": "physical-button-secret"},
        [],
    )

    assert "physical-button-secret" not in path.read_text(encoding="utf-8")
    loaded = persistence.load("owner-01")
    assert loaded is not None
    assert loaded["button_secrets"]["field-01"] == "physical-button-secret"


def test_runtime_session_state_survives_configuration_updates(tmp_path) -> None:
    persistence = FileConfigurationPersistence(str(tmp_path / "configuration.json"))
    persistence.initialize()
    persistence.save_runtime_state("owner-01", {"sessions": [{"id": "session-01"}]})
    persistence.save(
        "owner-01",
        {"id": "club-01", "name": "Club Norte", "city": "La Plata", "fields_count": 0},
        [], [], {}, {}, [],
    )

    loaded = persistence.load("owner-01")
    assert loaded is not None
    assert loaded["runtime_state"]["sessions"][0]["id"] == "session-01"


def test_runtime_updates_do_not_decrypt_configuration_file(tmp_path) -> None:
    path = tmp_path / "configuration.json"
    persistence = FileConfigurationPersistence(str(path))
    persistence.initialize()
    persistence.save(
        "owner-01",
        {"id": "club-01", "name": "Club Norte", "city": "", "fields_count": 0},
        [],
        [{
            "id": "camera-01", "field_id": "field-01", "name": "Tapo", "password": "camera-secret",
            "status": "ready", "last_seen": "ahora",
        }],
        {}, {}, [],
    )

    persistence.save_runtime_state("owner-01", {"sessions": []})

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["cameras"][0]["password"].startswith("encv1:")
    assert raw["runtime_state"] == {"sessions": []}
