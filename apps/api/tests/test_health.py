from fastapi.testclient import TestClient
from main import app


def test_health_reports_real_component_checks() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["checks"]["database"]["status"] == "disabled"
    assert payload["checks"]["storage"]["status"] == "ok"
    assert payload["checks"]["worker"]["status"] == "disabled"
    assert payload["checks"]["backup"]["status"] == "disabled"


def test_liveness_does_not_claim_dependency_readiness() -> None:
    response = TestClient(app).get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "vivoo-api"}
