from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from config import settings
from main import app
from services.store import DEMO_CAMERA_ID, DEMO_FIELD_ID, HighlightRecord, SessionRecord, store


client = TestClient(app)


def owner_headers() -> dict[str, str]:
    login = client.post(
        "/auth/login",
        json={"email": "owner@courtvision.local", "password": "courtvision-demo"},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def available_highlight() -> tuple[str, Path]:
    session_id = uuid4()
    event_id = uuid4()
    highlight_id = uuid4()
    now = datetime.now(timezone.utc)
    storage_key = f"highlights/monthly-{highlight_id}.mp4"
    store.sessions[session_id] = SessionRecord(
        id=session_id,
        token=f"session-{session_id}",
        field_id=DEMO_FIELD_ID,
        camera_id=DEMO_CAMERA_ID,
        sport_code="padel",
        started_at=now - timedelta(minutes=10),
    )
    store.highlights[highlight_id] = HighlightRecord(
        id=highlight_id,
        event_id=event_id,
        session_id=session_id,
        occurred_at=now,
        window_start_at=now - timedelta(seconds=30),
        window_end_at=now,
        duration_seconds=30,
        storage_key=storage_key,
        status="available",
        confidence=0.97,
    )
    media_path = Path(settings.local_media_root) / storage_key
    media_path.parent.mkdir(parents=True, exist_ok=True)
    media_path.write_bytes(b"monthly-favorite-video")
    return str(highlight_id), media_path


def test_owner_publishes_monthly_favorites_with_one_central_public_origin() -> None:
    highlight_id, media_path = available_highlight()
    store.club["name"] = "Pádel del Río"
    store.club["public_slug"] = ""
    try:
        response = client.put(
            "/owner/monthly-favorites",
            json={"highlight_ids": [highlight_id, highlight_id]},
            headers=owner_headers(),
        )
        assert response.status_code == 200
        page = response.json()
        assert page["public_slug"] == "padel-del-rio"
        assert page["public_path"] == "/padel-del-rio/destacados"
        assert page["public_url"] == f"{settings.public_app_base_url}/padel-del-rio/destacados"
        assert [item["id"] for item in page["items"]] == [highlight_id]

        selected_at = datetime.fromisoformat(page["items"][0]["selected_at"])
        expires_at = datetime.fromisoformat(page["items"][0]["expires_at"])
        assert expires_at - selected_at == timedelta(days=30)

        public = client.get("/public/clubs/padel-del-rio/monthly-favorites")
        assert public.status_code == 200
        public_item = public.json()["items"][0]
        assert public_item["id"] == highlight_id
        assert public_item["media_path"].endswith(f"/{highlight_id}/media")
        video = client.get(public_item["media_path"])
        assert video.status_code == 200
        assert video.content == b"monthly-favorite-video"
    finally:
        media_path.unlink(missing_ok=True)


def test_monthly_favorite_expires_automatically_and_can_be_removed_by_owner() -> None:
    highlight_id, media_path = available_highlight()
    store.club["name"] = "Club Test"
    store.club["public_slug"] = ""
    try:
        published = client.put(
            "/owner/monthly-favorites",
            json={"highlight_ids": [highlight_id]},
            headers=owner_headers(),
        ).json()
        slug = published["public_slug"]
        store.monthly_favorites[0].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        assert client.get(f"/public/clubs/{slug}/monthly-favorites").json()["items"] == []
        assert client.get(f"/public/clubs/{slug}/monthly-favorites/{highlight_id}/media").status_code == 404

        republished = client.put(
            "/owner/monthly-favorites",
            json={"highlight_ids": [highlight_id]},
            headers=owner_headers(),
        )
        assert len(republished.json()["items"]) == 1
        removed = client.put(
            "/owner/monthly-favorites",
            json={"highlight_ids": []},
            headers=owner_headers(),
        )
        assert removed.status_code == 200
        assert removed.json()["items"] == []
    finally:
        media_path.unlink(missing_ok=True)
