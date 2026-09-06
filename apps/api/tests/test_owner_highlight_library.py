import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from config import settings
from fastapi.testclient import TestClient
from main import app
from services.store import FULL_RECORDING_RETENTION, store


client = TestClient(app)


def owner_headers() -> dict[str, str]:
    login = client.post(
        "/auth/login",
        json={"email": "owner@courtvision.local", "password": "courtvision-demo"},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_owner_library_exposes_scoped_playback_and_download() -> None:
    session = client.post(
        "/public/fields/field-01/sessions",
        json={
            "display_name": "Martín Test",
            "phone_e164": "+5491155550198",
            "recording_consent": True,
            "messaging_consent": False,
        },
        headers={"Idempotency-Key": "owner-library-session"},
    )
    event = client.post(
        f"/agent/sessions/{session.json()['session_id']}/events",
        json={
            "source_id": "owner-library-event",
            "event_type": "manual",
            "confidence": 0.984,
            "occurred_at": "2026-09-01T22:00:30Z",
            "buffer_start_at": "2026-09-01T22:00:00Z",
            "buffer_end_at": "2026-09-01T22:00:30Z",
            "source_storage_key": "highlight-sources/owner-library.mp4",
        },
        headers={"Idempotency-Key": "owner-library-event", "Authorization": "Bearer courtvision-local-agent"},
    )
    job = client.get("/worker/jobs/next", headers={"Authorization": "Bearer courtvision-local-worker"}).json()
    media_path = Path(settings.local_media_root) / job["output_storage_key"]
    source_path = Path(settings.local_media_root) / "highlight-sources/owner-library.mp4"
    media_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.parent.mkdir(parents=True, exist_ok=True)
    media_path.write_bytes(b"owner-highlight-video")
    source_path.write_bytes(b"owner-highlight-source")
    try:
        completed = client.post(
            f"/worker/jobs/{job['job_id']}/complete",
            json={"succeeded": True, "output_storage_key": job["output_storage_key"]},
            headers={"Authorization": "Bearer courtvision-local-worker"},
        )
        assert completed.status_code == 204
        assert client.get("/owner/highlights").status_code == 401

        response = client.get("/owner/highlights", headers=owner_headers())
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["id"] == event.json()["highlight_id"]
        assert item["field_name"] == "Cancha 01"
        assert item["players"] == ["Martín Test"]
        assert item["duration_seconds"] == 30
        assert item["confidence"] == 0.984
        assert item["status"] == "available"

        playback = client.get(item["media_path"])
        assert playback.status_code == 200
        assert playback.content == b"owner-highlight-video"
        assert playback.headers["content-type"].startswith("video/mp4")

        download = client.get(item["download_path"])
        assert download.status_code == 200
        assert download.headers["content-disposition"].startswith("attachment")

        invalid_ticket = f"{item['media_path'][:-1]}x"
        assert client.get(invalid_ticket).status_code == 401

        assert client.delete(f"/owner/highlights/{item['id']}").status_code == 401
        deleted = client.delete(f"/owner/highlights/{item['id']}", headers=owner_headers())
        assert deleted.status_code == 204
        assert not media_path.exists()
        assert not source_path.exists()
        assert client.get("/owner/highlights", headers=owner_headers()).json()["items"] == []
        assert client.get(item["media_path"]).status_code == 404
        player_page = client.get(f"/public/access/{session.json()['access_token']}")
        assert player_page.json()["highlights"] == []
    finally:
        media_path.unlink(missing_ok=True)
        source_path.unlink(missing_ok=True)


def test_owner_can_delete_multiple_highlights_in_one_operation() -> None:
    session = client.post(
        "/public/fields/field-01/sessions",
        json={
            "display_name": "Selección Test",
            "phone_e164": "+5491155550197",
            "recording_consent": True,
            "messaging_consent": False,
        },
        headers={"Idempotency-Key": "batch-library-session"},
    )
    highlight_ids: list[str] = []
    paths: list[Path] = []
    try:
        for index in range(2):
            source_key = f"highlight-sources/batch-library-{index}.mp4"
            event = client.post(
                f"/agent/sessions/{session.json()['session_id']}/events",
                json={
                    "source_id": f"batch-library-event-{index}",
                    "event_type": "manual",
                    "occurred_at": f"2026-09-01T22:0{index}:30Z",
                    "source_storage_key": source_key,
                },
                headers={
                    "Idempotency-Key": f"batch-library-event-{index}",
                    "Authorization": "Bearer courtvision-local-agent",
                },
            )
            highlight_ids.append(event.json()["highlight_id"])
            job = client.get("/worker/jobs/next", headers={"Authorization": "Bearer courtvision-local-worker"}).json()
            output_path = Path(settings.local_media_root) / job["output_storage_key"]
            source_path = Path(settings.local_media_root) / source_key
            output_path.parent.mkdir(parents=True, exist_ok=True)
            source_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"video")
            source_path.write_bytes(b"source")
            paths.extend((output_path, source_path))
            assert client.post(
                f"/worker/jobs/{job['job_id']}/complete",
                json={"succeeded": True, "output_storage_key": job["output_storage_key"]},
                headers={"Authorization": "Bearer courtvision-local-worker"},
            ).status_code == 204

        deleted = client.post(
            "/owner/highlights/delete-batch",
            json={"highlight_ids": [*highlight_ids, highlight_ids[0]]},
            headers=owner_headers(),
        )
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] == 2
        assert client.get("/owner/highlights", headers=owner_headers()).json()["items"] == []
        assert all(not path.exists() for path in paths)
    finally:
        for path in paths:
            path.unlink(missing_ok=True)


def _create_available_recording(index: int = 0) -> tuple[dict, Path]:
    content = f"whole-match-{index}".encode()
    checksum = hashlib.sha256(content).hexdigest()
    session = client.post(
        "/public/fields/field-01/sessions",
        json={
            "display_name": f"Jugador {index}",
            "phone_e164": f"+54911555502{index:02d}",
            "recording_consent": True,
            "messaging_consent": False,
        },
        headers={"Idempotency-Key": f"owner-recording-session-{index}"},
    )
    reservation = client.post(
        "/agent/uploads/presign",
        json={
            "session_id": session.json()["session_id"],
            "media_type": "recording",
            "content_type": "video/mp4",
            "size_bytes": len(content),
            "checksum": checksum,
        },
        headers={"Authorization": "Bearer courtvision-local-agent"},
    )
    storage_key = reservation.json()["storage_key"]
    media_path = Path(settings.local_media_root) / storage_key
    media_path.parent.mkdir(parents=True, exist_ok=True)
    media_path.write_bytes(content)
    completed = client.post(
        "/agent/uploads/complete",
        json={
            "session_id": session.json()["session_id"],
            "media_type": "recording",
            "storage_key": storage_key,
            "size_bytes": len(content),
            "checksum": checksum,
        },
        headers={"Authorization": "Bearer courtvision-local-agent"},
    )
    assert completed.status_code == 204
    return session.json(), media_path


def test_owner_library_exposes_full_recordings_for_playback_download_and_delete() -> None:
    session, media_path = _create_available_recording()
    try:
        assert client.get("/owner/recordings").status_code == 401
        response = client.get("/owner/recordings", headers=owner_headers())
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["title"] == "Partido completo"
        assert item["session_id"] == session["session_id"]
        assert item["field_name"] == "Cancha 01"
        assert item["players"] == ["Jugador 0"]
        assert item["status"] == "available"

        playback = client.get(item["media_path"])
        assert playback.status_code == 200
        assert playback.content == b"whole-match-0"
        download = client.get(item["download_path"])
        assert download.status_code == 200
        assert download.headers["content-disposition"].startswith("attachment")

        deleted = client.delete(f"/owner/recordings/{item['id']}", headers=owner_headers())
        assert deleted.status_code == 204
        assert not media_path.exists()
        assert client.get("/owner/recordings", headers=owner_headers()).json()["items"] == []
        player_page = client.get(f"/public/access/{session['access_token']}")
        assert player_page.json()["recording_path"] is None
    finally:
        media_path.unlink(missing_ok=True)


def test_owner_can_delete_multiple_full_recordings() -> None:
    paths: list[Path] = []
    try:
        for index in range(2):
            _, path = _create_available_recording(index + 1)
            paths.append(path)
        items = client.get("/owner/recordings", headers=owner_headers()).json()["items"]
        deleted = client.post(
            "/owner/recordings/delete-batch",
            json={"recording_ids": [items[0]["id"], items[1]["id"], items[0]["id"]]},
            headers=owner_headers(),
        )
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] == 2
        assert client.get("/owner/recordings", headers=owner_headers()).json()["items"] == []
        assert all(not path.exists() for path in paths)
    finally:
        for path in paths:
            path.unlink(missing_ok=True)


def test_full_recording_is_unavailable_and_deleted_after_48_hours() -> None:
    session, media_path = _create_available_recording(9)
    session_record = store.sessions[UUID(session["session_id"])]
    session_record.ended_at = datetime.now(timezone.utc) - FULL_RECORDING_RETENTION - timedelta(seconds=1)
    try:
        player_page = client.get(f"/public/access/{session['access_token']}")
        assert player_page.status_code == 200
        assert player_page.json()["recording_status"] == "expired"
        assert player_page.json()["recording_path"] is None
        assert client.get("/owner/recordings", headers=owner_headers()).json()["items"] == []

        heartbeat = client.post(
            "/worker/heartbeat",
            headers={"Authorization": "Bearer courtvision-local-worker"},
        )
        assert heartbeat.status_code == 204
        assert not media_path.exists()
        assert store.recordings == {}
    finally:
        media_path.unlink(missing_ok=True)
