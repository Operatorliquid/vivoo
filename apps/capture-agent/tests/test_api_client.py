import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from client.api_client import AgentApiClient
from inference.events import manual_event


class FakeResponse:
    def __init__(self, status: int = 200, body: bytes = b"{}") -> None:
        self.status = status
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body


def test_client_reuses_source_id_as_idempotency_key() -> None:
    requests = []

    def opener(request, timeout):
        requests.append(request)
        return FakeResponse(body=b'{"status":"processing"}')

    client = AgentApiClient("http://api.local", "agent-secret", opener=opener)
    result = client.submit_event(UUID("00000000-0000-0000-0000-000000000001"), manual_event(datetime.now(timezone.utc)))
    assert result["status"] == "processing"
    assert requests[0].get_header("Idempotency-key").startswith("manual-")
    assert requests[0].get_header("Authorization") == "Bearer agent-secret"


def test_client_presign_includes_checksum_and_size(tmp_path: Path) -> None:
    source = tmp_path / "segment.mp4"
    source.write_bytes(b"video-segment")
    requests = []

    def opener(request, timeout):
        requests.append(request)
        return FakeResponse(body=b'{"upload_url":"http://upload.local/x","storage_key":"x","expires_at":"2026-08-11T12:00:00Z"}')

    client = AgentApiClient("http://api.local", "agent-secret", opener=opener)
    result = client.presign_upload(UUID("00000000-0000-0000-0000-000000000001"), "segment", "video/mp4", source)
    body = json.loads(requests[0].data)
    assert body["size_bytes"] == len(b"video-segment")
    assert body["checksum"] == result["checksum"]
