import json
from io import BytesIO
from types import SimpleNamespace
from urllib.error import HTTPError

import services.evolution_service as evolution_module
from services.evolution_service import EvolutionService, owner_instance_name


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def test_owner_instance_names_are_stable_and_isolated() -> None:
    assert owner_instance_name("owner-one") == owner_instance_name("owner-one")
    assert owner_instance_name("owner-one") != owner_instance_name("owner-two")
    assert "owner-one" not in owner_instance_name("owner-one")


def test_connect_creates_owner_instance_and_returns_qr_without_api_key(monkeypatch) -> None:
    monkeypatch.setattr(
        evolution_module,
        "settings",
        SimpleNamespace(
            evolution_enabled=True,
            evolution_api_url="http://evolution.local",
            evolution_api_key="global-private-key",
        ),
    )
    requests = []

    def opener(request, timeout):
        requests.append(request)
        if "/connectionState/" in request.full_url:
            raise HTTPError(request.full_url, 404, "missing", {}, BytesIO(b'{}'))
        if request.full_url.endswith("/instance/create"):
            return FakeResponse({"instance": {"state": "close"}})
        return FakeResponse({"base64": "data:image/png;base64,qr", "pairingCode": "12345678"})

    connection = EvolutionService(opener=opener).connect("owner-one")

    assert connection.status == "connecting"
    assert connection.qr_base64 == "data:image/png;base64,qr"
    assert connection.pairing_code == "12345678"
    assert "global-private-key" not in json.dumps(connection.as_dict())
    assert requests[-1].get_header("Apikey") == "global-private-key"
