from __future__ import annotations

import hashlib
import http.client
import json
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import UUID

from inference.events import NormalizedCaptureEvent


class AgentApiError(RuntimeError):
    pass


class AgentApiClient:
    def __init__(self, base_url: str, agent_key: str, timeout_seconds: float = 10, max_retries: int = 3, opener: Callable = urlopen) -> None:
        self.base_url = base_url.rstrip("/")
        self.agent_key = agent_key
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)
        self._opener = opener

    def _request(self, method: str, path: str, payload: dict | None = None, idempotency_key: str | None = None) -> tuple[int, bytes]:
        headers = {"Authorization": f"Bearer {self.agent_key}", "Accept": "application/json"}
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode("utf-8")
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        request = Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        for attempt in range(self.max_retries + 1):
            try:
                with self._opener(request, timeout=self.timeout_seconds) as response:
                    return response.status, response.read()
            except HTTPError as error:
                detail = error.read().decode("utf-8", errors="replace")
                retryable = error.code in {408, 429, 500, 502, 503, 504}
                if not retryable or attempt == self.max_retries:
                    raise AgentApiError(f"{error.code}: {detail}") from error
            except OSError as error:
                if attempt == self.max_retries:
                    raise AgentApiError("Capture API unavailable") from error
            time.sleep(min(0.25 * (2 ** attempt), 2))
        raise AgentApiError("Capture API unavailable")

    def heartbeat(
        self,
        device_id: str,
        camera_status: str,
        observed_at: datetime,
        agent_version: str,
        active_session_id: UUID | None = None,
        detector_status: str | None = None,
        detector_fps: float | None = None,
        detector_last_frame_at: str | None = None,
    ) -> None:
        self._request("POST", "/agent/heartbeat", {
            "device_id": device_id,
            "observed_at": observed_at.isoformat(),
            "camera_status": camera_status,
            "active_session_id": str(active_session_id) if active_session_id else None,
            "agent_version": agent_version,
            "detector_status": detector_status,
            "detector_fps": detector_fps,
            "detector_last_frame_at": detector_last_frame_at,
        })

    def get_camera_config(self, camera_id: str) -> dict:
        _, body = self._request("GET", f"/agent/cameras/{camera_id}/config")
        return json.loads(body)

    def submit_event(self, session_id: UUID, event: NormalizedCaptureEvent, source_storage_key: str | None = None) -> dict:
        payload = asdict(event)
        if source_storage_key:
            payload["source_storage_key"] = source_storage_key
        for key, value in tuple(payload.items()):
            if value is not None and isinstance(value, datetime):
                payload[key] = value.isoformat()
            elif value is None:
                payload.pop(key)
        _, body = self._request("POST", f"/agent/sessions/{session_id}/events", payload, event.source_id)
        return json.loads(body)

    def presign_upload(self, session_id: UUID, media_type: str, content_type: str, source_path: Path) -> dict:
        digest = hashlib.sha256()
        with source_path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        checksum = digest.hexdigest()
        size_bytes = source_path.stat().st_size
        _, body = self._request("POST", "/agent/uploads/presign", {
            "session_id": str(session_id),
            "media_type": media_type,
            "content_type": content_type,
            "size_bytes": size_bytes,
            "checksum": checksum,
        })
        return json.loads(body) | {"checksum": checksum, "size_bytes": size_bytes}

    def upload_file(self, upload_url: str, source_path: Path, content_type: str, checksum: str) -> None:
        parsed = urlsplit(upload_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise AgentApiError("Media upload URL inválida")
        request_path = parsed.path or "/"
        if parsed.query:
            request_path += f"?{parsed.query}"
        size_bytes = source_path.stat().st_size
        cloud_origin = urlsplit(self.base_url)
        is_local_api_upload = parsed.hostname == cloud_origin.hostname and parsed.port == cloud_origin.port
        for attempt in range(self.max_retries + 1):
            connection_class = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
            connection = connection_class(parsed.hostname, parsed.port, timeout=self.timeout_seconds)
            try:
                connection.putrequest("PUT", request_path)
                connection.putheader("Content-Type", content_type)
                connection.putheader("Content-Length", str(size_bytes))
                connection.putheader("x-amz-meta-sha256", checksum)
                if is_local_api_upload:
                    connection.putheader("Authorization", f"Bearer {self.agent_key}")
                connection.endheaders()
                with source_path.open("rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        connection.send(chunk)
                response = connection.getresponse()
                response.read()
                if 200 <= response.status < 300:
                    return
                if response.status not in {408, 429, 500, 502, 503, 504} or attempt == self.max_retries:
                    raise AgentApiError(f"{response.status}: upload rejected")
            except OSError as error:
                if attempt == self.max_retries:
                    raise AgentApiError("Media upload unavailable") from error
            finally:
                connection.close()
            time.sleep(min(0.25 * (2 ** attempt), 2))

    def _upload_part(self, upload_id: str, part_number: int, chunk: bytes, content_type: str) -> None:
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise AgentApiError("Capture API URL inválida")
        base_path = parsed.path.rstrip("/")
        request_path = f"{base_path}/agent/uploads/resumable/{upload_id}/parts/{part_number}"
        for attempt in range(self.max_retries + 1):
            connection_class = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
            connection = connection_class(parsed.hostname, parsed.port, timeout=max(self.timeout_seconds, 30))
            try:
                connection.putrequest("PUT", request_path)
                connection.putheader("Content-Type", content_type)
                connection.putheader("Content-Length", str(len(chunk)))
                connection.putheader("Authorization", f"Bearer {self.agent_key}")
                connection.endheaders(chunk)
                response = connection.getresponse()
                response.read()
                if 200 <= response.status < 300:
                    return
                if response.status not in {408, 429, 500, 502, 503, 504} or attempt == self.max_retries:
                    raise AgentApiError(f"{response.status}: upload part rejected")
            except OSError as error:
                if attempt == self.max_retries:
                    raise AgentApiError("Media upload unavailable") from error
            finally:
                connection.close()
            time.sleep(min(0.25 * (2 ** attempt), 2))

    def upload_resumable(self, session_id: UUID, media_type: str, content_type: str, source_path: Path) -> dict:
        digest = hashlib.sha256()
        with source_path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        checksum = digest.hexdigest()
        size_bytes = source_path.stat().st_size
        _, body = self._request("POST", "/agent/uploads/resumable", {
            "session_id": str(session_id), "media_type": media_type,
            "content_type": content_type, "size_bytes": size_bytes, "checksum": checksum,
        })
        reservation = json.loads(body)
        upload_id = str(reservation["upload_id"])
        part_size = int(reservation["part_size"])
        received = {int(number) for number in reservation.get("received_parts", [])}
        with source_path.open("rb") as source:
            part_number = 1
            while chunk := source.read(part_size):
                if part_number not in received:
                    self._upload_part(upload_id, part_number, chunk, content_type)
                part_number += 1
        self._request("POST", f"/agent/uploads/resumable/{upload_id}/complete", {
            "session_id": str(session_id), "media_type": media_type, "upload_id": upload_id,
            "storage_key": str(reservation["storage_key"]), "size_bytes": size_bytes, "checksum": checksum,
        })
        return reservation | {"checksum": checksum, "size_bytes": size_bytes}

    def complete_upload(self, session_id: UUID, media_type: str, storage_key: str, size_bytes: int, checksum: str) -> None:
        self._request("POST", "/agent/uploads/complete", {
            "session_id": str(session_id),
            "media_type": media_type,
            "storage_key": storage_key,
            "size_bytes": size_bytes,
            "checksum": checksum,
        })
