from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def _admin_token() -> str:
    response = client.post(
        "/admin/auth/login",
        json={"email": "admin@tveo.local", "password": "tveo-admin-demo"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_admin_can_read_real_customer_operation() -> None:
    token = _admin_token()
    response = client.get("/admin/overview", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["customers"] == 1
    assert body["summary"]["courts"] == len(body["customers"][0]["courts"])
    assert body["customers"][0]["email"] == "owner@courtvision.local"
    assert body["customers"][0]["status"] in {"operational", "attention", "setup"}


def test_owner_and_admin_permissions_are_isolated() -> None:
    owner = client.post(
        "/auth/login",
        json={"email": "owner@courtvision.local", "password": "courtvision-demo"},
    ).json()["access_token"]
    admin = _admin_token()

    assert client.get("/admin/overview", headers={"Authorization": f"Bearer {owner}"}).status_code == 403
    assert client.get("/owner/dashboard", headers={"Authorization": f"Bearer {admin}"}).status_code == 401
    assert client.post(
        "/auth/login", json={"email": "admin@tveo.local", "password": "tveo-admin-demo"}
    ).status_code == 401


def test_admin_session_rotates_and_logs_out() -> None:
    token = _admin_token()
    rotated = client.post("/admin/auth/refresh", headers={"Authorization": f"Bearer {token}"})
    assert rotated.status_code == 200
    replacement = rotated.json()["access_token"]
    assert replacement != token
    assert client.get("/admin/overview", headers={"Authorization": f"Bearer {token}"}).status_code == 403
    assert client.post("/admin/auth/logout", headers={"Authorization": f"Bearer {replacement}"}).status_code == 204
    assert client.get("/admin/overview", headers={"Authorization": f"Bearer {replacement}"}).status_code == 403


def test_admin_creates_an_isolated_owner_that_can_use_the_dashboard() -> None:
    admin = _admin_token()
    payload = {
        "display_name": "Ana Operadora",
        "email": "ana.owner@example.com",
        "password": "owner-secure-2026",
        "club_name": "Pádel Norte",
        "city": "Rosario",
    }
    created = client.post(
        "/admin/customers", json=payload, headers={"Authorization": f"Bearer {admin}"}
    )
    assert created.status_code == 201
    assert created.json()["club"]["name"] == "Pádel Norte"
    assert created.json()["metrics"]["courts"] == 0

    duplicate = client.post(
        "/admin/customers", json=payload, headers={"Authorization": f"Bearer {admin}"}
    )
    assert duplicate.status_code == 409

    login = client.post(
        "/auth/login", json={"email": payload["email"], "password": payload["password"]}
    )
    assert login.status_code == 200
    owner = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {owner}"}
    dashboard = client.get("/owner/dashboard", headers=headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["club"]["name"] == "Pádel Norte"
    assert client.get("/owner/fields", headers=headers).json()["items"] == []

    field = client.post(
        "/owner/fields",
        json={"name": "Cancha Central", "sport_code": "padel", "detection_mode": "arms_up"},
        headers=headers,
    )
    assert field.status_code == 200
    assert field.json()["name"] == "Cancha Central"
    assert len(client.get("/owner/fields", headers=headers).json()["items"]) == 1
