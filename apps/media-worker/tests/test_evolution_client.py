import json
from urllib.error import HTTPError

from delivery.evolution_client import EvolutionApiClient, EvolutionConfig


class FakeResponse:
    status = 201

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b'{"status":"PENDING"}'


def test_evolution_sends_video_media_payload() -> None:
    requests = []

    def opener(request, timeout):
        requests.append(request)
        if "/connectionState/" in request.full_url:
            return type("StateResponse", (FakeResponse,), {"read": lambda self: b'{"instance":{"state":"open"}}'})()
        return FakeResponse()

    client = EvolutionApiClient(EvolutionConfig("http://evolution.local", "secret", "courtvision", enabled=True), opener=opener)
    response = client.send_video("+5491155550118", "https://cdn.example/highlight.mp4", "Tu highlight")
    assert response["status"] == "PENDING"
    assert requests[-1].full_url == "http://evolution.local/message/sendMedia/courtvision"
    assert requests[-1].get_header("Apikey") == "secret"
    assert json.loads(requests[-1].data)["mediatype"] == "video"


def test_evolution_retries_transient_failures() -> None:
    attempts = []

    def opener(request, timeout):
        attempts.append(request)
        if "/connectionState/" in request.full_url:
            return type("StateResponse", (FakeResponse,), {"read": lambda self: b'{"instance":{"state":"open"}}'})()
        send_attempts = [item for item in attempts if "/sendMedia/" in item.full_url]
        if len(send_attempts) < 3:
            raise HTTPError(request.full_url, 503, "unavailable", {}, None)
        return FakeResponse()

    client = EvolutionApiClient(
        EvolutionConfig("http://evolution.local", "secret", "fallback", enabled=True),
        opener=opener,
        max_retries=3,
        sleeper=lambda _seconds: None,
    )
    response = client.send_video("+5491155550118", "https://cdn.example/highlight.mp4", "Listo", instance="tveo-owner")

    assert response["status"] == "PENDING"
    assert len([item for item in attempts if "/sendMedia/" in item.full_url]) == 3
    assert attempts[-1].full_url.endswith("/message/sendMedia/tveo-owner")


def test_evolution_exposes_safe_error_detail() -> None:
    def opener(request, timeout):
        if "/connectionState/" in request.full_url:
            return type("StateResponse", (FakeResponse,), {"read": lambda self: b'{"instance":{"state":"open"}}'})()
        raise HTTPError(request.full_url, 400, "bad request", {}, __import__('io').BytesIO(b'{"message":"invalid number"}'))

    client = EvolutionApiClient(
        EvolutionConfig("http://evolution.local", "secret", "courtvision", enabled=True),
        opener=opener,
        max_retries=0,
    )

    try:
        client.send_video("+5492227462048", "https://cdn.example/highlight.mp4", "Listo")
    except Exception as error:
        assert 'invalid number' in str(error)
    else:
        raise AssertionError('Expected Evolution error')


def test_evolution_repairs_a_persisted_session_before_sending() -> None:
    requests = []

    def opener(request, timeout):
        requests.append(request.full_url)
        if "/connectionState/" in request.full_url:
            state = "close" if requests.count(request.full_url) == 1 else "open"
            return type("StateResponse", (FakeResponse,), {"read": lambda self: json.dumps({"instance": {"state": state}}).encode()})()
        if "/instance/connect/" in request.full_url:
            return type("ReconnectResponse", (FakeResponse,), {"read": lambda self: b'{"instance":{"state":"open"}}'})()
        return FakeResponse()

    client = EvolutionApiClient(
        EvolutionConfig("http://evolution.local", "secret", "courtvision", enabled=True),
        opener=opener, sleeper=lambda _seconds: None,
    )
    client.send_video("+5491155550118", "https://cdn.example/highlight.mp4", "Listo")

    assert any("/instance/connect/courtvision" in url for url in requests)
    assert requests[-1].endswith("/message/sendMedia/courtvision")
