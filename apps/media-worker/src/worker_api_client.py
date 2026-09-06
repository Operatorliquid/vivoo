from __future__ import annotations

import json
from typing import Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID


class WorkerApiError(RuntimeError):
    pass


class WorkerApiClient:
    def __init__(self, base_url: str, worker_key: str, opener: Callable = urlopen) -> None:
        self.base_url = base_url.rstrip("/")
        self.worker_key = worker_key
        self._opener = opener

    def _request(self, method: str, path: str, payload: dict | None = None) -> tuple[int, bytes]:
        headers = {"Authorization": f"Bearer {self.worker_key}", "Accept": "application/json"}
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode("utf-8")
        request = Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        try:
            with self._opener(request, timeout=10) as response:
                return response.status, response.read()
        except HTTPError as error:
            raise WorkerApiError(f"{error.code}: worker API error") from error
        except OSError as error:
            raise WorkerApiError("Worker API unavailable") from error

    def lease_next_job(self) -> dict | None:
        status_code, body = self._request("GET", "/worker/jobs/next")
        return json.loads(body) if status_code != 204 and body else None

    def heartbeat(self) -> None:
        self._request("POST", "/worker/heartbeat")

    def complete_job(self, job_id: UUID, succeeded: bool, output_storage_key: str | None = None, error: str | None = None) -> None:
        self._request("POST", f"/worker/jobs/{job_id}/complete", {
            "succeeded": succeeded,
            "output_storage_key": output_storage_key,
            "error": error,
        })

    def report_delivery(self, job_id: UUID, phone_e164: str, display_name: str, succeeded: bool, error: str | None = None) -> None:
        self._request("POST", f"/worker/jobs/{job_id}/delivery", {
            "phone_e164": phone_e164,
            "display_name": display_name,
            "succeeded": succeeded,
            "error": error,
        })
