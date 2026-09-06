from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi.testclient import TestClient

from main import app
from services.store import MAX_SESSION_DURATION, store


client = TestClient(app)


def owner_headers() -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"email": "owner@courtvision.local", "password": "courtvision-demo"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def player_payload() -> dict[str, object]:
    return {
        "display_name": "Jugador de prueba",
        "phone_e164": "+5491155550188",
        "recording_consent": True,
        "messaging_consent": False,
    }


def test_qr_registration_requests_recording_and_agent_acknowledges_it() -> None:
    before = client.get("/public/fields/field-01")
    assert before.status_code == 200
    assert before.json()["camera_status"] == "live"
    assert before.json()["recording_status"] == "idle"

    session = client.post(
        "/public/fields/field-01/sessions",
        json=player_payload(),
        headers={"Idempotency-Key": "qr-recording-start"},
    )
    assert session.status_code == 201
    access_token = session.json()["access_token"]
    player_page = client.get(f"/public/access/{access_token}")
    assert player_page.status_code == 200
    assert player_page.json()["recording_status"] == "in_progress"
    assert player_page.json()["recording_path"] is None

    field = next(item for item in client.get("/owner/fields", headers=owner_headers()).json()["items"] if item["id"] == "field-01")
    assert field["active_session_id"] == session.json()["session_id"]
    assert field["recording"]["status"] == "starting"
    assert field["recording"]["started_by"] == "player"
    assert client.get("/public/fields/field-01").json()["recording_status"] == "starting"

    heartbeat = client.post(
        "/agent/heartbeat",
        json={
            "device_id": "camera-01",
            "observed_at": "2026-09-01T20:00:00Z",
            "camera_status": "online",
            "active_session_id": session.json()["session_id"],
            "agent_version": "0.5.0",
            "detector_status": "running",
            "detector_fps": 4.8,
            "detector_last_frame_at": "2026-09-01T20:00:00Z",
        },
        headers={"Authorization": "Bearer courtvision-local-agent"},
    )
    assert heartbeat.status_code == 204
    field = next(item for item in client.get("/owner/fields", headers=owner_headers()).json()["items"] if item["id"] == "field-01")
    assert field["recording"]["status"] == "recording"
    assert field["camera"]["detector_status"] == "running"
    assert field["camera"]["detector_fps"] == 4.8
    assert client.get("/public/fields/field-01").json()["recording_status"] == "recording"


def test_owner_can_start_and_stop_the_same_session_players_join() -> None:
    headers = owner_headers()
    started = client.post("/owner/fields/field-01/recording/start", headers=headers)
    assert started.status_code == 200
    session_id = started.json()["active_session_id"]
    assert started.json()["recording"]["started_by"] == "owner"

    joined = client.post(
        "/public/fields/field-01/sessions",
        json=player_payload(),
        headers={"Idempotency-Key": "join-owner-recording"},
    )
    assert joined.status_code == 201
    assert joined.json()["session_id"] == session_id
    access_token = joined.json()["access_token"]

    duplicate_start = client.post("/owner/fields/field-01/recording/start", headers=headers)
    assert duplicate_start.status_code == 200
    assert duplicate_start.json()["active_session_id"] == session_id

    stopped = client.post("/owner/fields/field-01/recording/stop", headers=headers)
    assert stopped.status_code == 200
    assert stopped.json()["active_session_id"] is None
    assert stopped.json()["recording"]["status"] == "idle"
    assert client.get(f"/public/access/{access_token}").json()["recording_status"] == "processing"

    config = client.get(
        "/agent/cameras/camera-01/config",
        headers={"Authorization": "Bearer courtvision-local-agent"},
    )
    assert config.status_code == 200
    assert config.json()["active_session_id"] is None


def test_each_new_field_qr_registration_rotates_to_a_new_match() -> None:
    first = client.post(
        "/public/fields/field-01/sessions",
        json=player_payload(),
        headers={"Idempotency-Key": "first-match"},
    )
    assert first.status_code == 201
    first_session_id = first.json()["session_id"]

    second_payload = {**player_payload(), "display_name": "Jugador del partido siguiente"}
    second = client.post(
        "/public/fields/field-01/sessions",
        json=second_payload,
        headers={"Idempotency-Key": "second-match"},
    )
    assert second.status_code == 201
    second_session_id = second.json()["session_id"]
    assert second_session_id != first_session_id
    assert store.sessions[UUID(first_session_id)].ended_at is not None
    assert store.sessions[UUID(second_session_id)].ended_at is None

    retry = client.post(
        "/public/fields/field-01/sessions",
        json=second_payload,
        headers={"Idempotency-Key": "second-match"},
    )
    assert retry.status_code == 201
    assert retry.json()["session_id"] == second_session_id
    assert len(store.sessions) == 2


def test_second_qr_registration_rotates_an_owner_started_match() -> None:
    headers = owner_headers()
    started = client.post("/owner/fields/field-01/recording/start", headers=headers)
    owner_session_id = started.json()["active_session_id"]

    first = client.post(
        "/public/fields/field-01/sessions",
        json=player_payload(),
        headers={"Idempotency-Key": "owner-match-first-player"},
    )
    assert first.json()["session_id"] == owner_session_id

    second = client.post(
        "/public/fields/field-01/sessions",
        json={**player_payload(), "display_name": "Nuevo partido"},
        headers={"Idempotency-Key": "owner-match-next-player"},
    )
    assert second.status_code == 201
    assert second.json()["session_id"] != owner_session_id
    assert store.sessions[UUID(owner_session_id)].ended_at is not None


def test_recording_stops_automatically_after_one_hour() -> None:
    session = client.post(
        "/public/fields/field-01/sessions",
        json=player_payload(),
        headers={"Idempotency-Key": "one-hour-timeout"},
    )
    session_record = store.sessions[UUID(session.json()["session_id"])]
    session_record.started_at = datetime.now(timezone.utc) - MAX_SESSION_DURATION - timedelta(seconds=5)

    config = client.get(
        "/agent/cameras/camera-01/config",
        headers={"Authorization": "Bearer courtvision-local-agent"},
    )
    assert config.status_code == 200
    assert config.json()["active_session_id"] is None
    assert session_record.ended_at == session_record.started_at + MAX_SESSION_DURATION


def test_owner_start_requires_an_available_camera() -> None:
    headers = owner_headers()
    created = client.post(
        "/owner/fields",
        headers=headers,
        json={"name": "Cancha sin cámara", "sport_code": "padel", "detection_mode": "arms_up"},
    )
    response = client.post(f"/owner/fields/{created.json()['id']}/recording/start", headers=headers)
    assert response.status_code == 409
    assert "cámara" in response.json()["detail"].lower()
