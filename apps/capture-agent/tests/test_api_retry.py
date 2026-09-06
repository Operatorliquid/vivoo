from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from client.api_client import AgentApiClient, AgentApiError


class RetryResponse:
    status = 204

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b""


def test_retries_transient_api_failures() -> None:
    attempts = []

    def opener(request: Request, timeout: float):
        attempts.append(request)
        if len(attempts) < 3:
            raise HTTPError(request.full_url, 503, "busy", {}, None)
        return RetryResponse()

    AgentApiClient("http://api.local", "agent-secret", max_retries=2, opener=opener).heartbeat(
        "camera-01", "online", datetime.now(timezone.utc), "0.1.0"
    )
    assert len(attempts) == 3


def test_does_not_retry_validation_failures() -> None:
    attempts = []

    def opener(request: Request, timeout: float):
        attempts.append(request)
        raise HTTPError(request.full_url, 401, "unauthorized", {}, None)

    with pytest.raises(AgentApiError):
        AgentApiClient("http://api.local", "wrong", max_retries=3, opener=opener).heartbeat(
            "camera-01", "online", datetime.now(timezone.utc), "0.1.0"
        )
    assert len(attempts) == 1
