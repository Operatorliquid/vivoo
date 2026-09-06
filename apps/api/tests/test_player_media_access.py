from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from main import app
from services.store import store


client = TestClient(app)


def _session() -> dict:
    response = client.post(
        "/public/fields/demo-field-02/sessions",
        json={
            "display_name": "Acceso privado",
            "phone_e164": "+5491155550123",
            "recording_consent": True,
            "messaging_consent": True,
            "policy_version": "2026-09",
        },
        headers={"Idempotency-Key": "private-access-test"},
    )
    assert response.status_code == 201
    return response.json()


def _owner_headers() -> dict[str, str]:
    login = client.post(
        "/auth/login",
        json={"email": "owner@courtvision.local", "password": "courtvision-demo"},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_private_access_is_opaque_and_expires() -> None:
    session = _session()
    token = session["access_token"]
    assert token.startswith("pa.")
    assert client.get(f"/public/access/{token}").status_code == 200

    access = store.player_access[store._access_hash(token)]
    access.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    expired = client.get(f"/public/access/{token}")
    assert expired.status_code == 410


def test_owner_can_revoke_every_player_link_for_a_session() -> None:
    session = _session()
    revoked = client.post(
        f"/owner/sessions/{session['session_id']}/access/revoke",
        headers=_owner_headers(),
    )
    assert revoked.status_code == 200
    assert revoked.json()["revoked"] == 1
    assert client.get(f"/public/access/{session['access_token']}").status_code == 410
