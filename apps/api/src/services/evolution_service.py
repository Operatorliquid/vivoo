from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from typing import Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from config import settings


class EvolutionServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class WhatsAppConnection:
    status: str
    instance_name: str
    phone: str | None = None
    profile_name: str | None = None
    qr_base64: str | None = None
    pairing_code: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "status": self.status,
            "instance_name": self.instance_name,
            "phone": self.phone,
            "profile_name": self.profile_name,
            "qr_base64": self.qr_base64,
            "pairing_code": self.pairing_code,
        }


def owner_instance_name(owner_id: str) -> str:
    """Stable, opaque Evolution instance name for one vivoo owner."""
    digest = hashlib.sha256(owner_id.encode("utf-8")).hexdigest()[:20]
    return f"tveo-{digest}"


class EvolutionService:
    def __init__(self, opener: Callable = urlopen) -> None:
        self._opener = opener
        self._reconnect_after: dict[str, float] = {}
        self._lock = threading.Lock()

    @property
    def configured(self) -> bool:
        return bool(settings.evolution_enabled and settings.evolution_api_url and settings.evolution_api_key)

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        if not self.configured:
            raise EvolutionServiceError("El servicio de WhatsApp todavía no está disponible")
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            f"{settings.evolution_api_url.rstrip('/')}{path}",
            data=body,
            headers={"Accept": "application/json", "Content-Type": "application/json", "apikey": settings.evolution_api_key},
            method=method,
        )
        try:
            with self._opener(request, timeout=15) as response:
                raw = response.read()
                return json.loads(raw.decode("utf-8")) if raw else {}
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise EvolutionServiceError(f"Evolution API devolvió {error.code}: {detail[:160]}") from error
        except (OSError, json.JSONDecodeError) as error:
            raise EvolutionServiceError("No pudimos comunicarnos con Evolution API") from error

    @staticmethod
    def _connection(instance_name: str, payload: dict, *, include_qr: bool = False) -> WhatsAppConnection:
        instance = payload.get("instance") if isinstance(payload.get("instance"), dict) else payload
        state = str(instance.get("state") or instance.get("connectionStatus") or "close").lower()
        status = "connected" if state == "open" else "connecting" if state in {"connecting", "qr"} else "disconnected"
        qr = payload.get("qrcode") if isinstance(payload.get("qrcode"), dict) else payload
        qr_base64 = (str(qr.get("base64") or "") or None) if include_qr else None
        pairing_code = (str(qr.get("pairingCode") or "") or None) if include_qr else None
        return WhatsAppConnection(
            status=status,
            instance_name=instance_name,
            phone=str(instance.get("ownerJid") or instance.get("number") or "") or None,
            profile_name=str(instance.get("profileName") or "") or None,
            qr_base64=qr_base64,
            pairing_code=pairing_code,
        )

    def _status(self, instance_name: str) -> WhatsAppConnection:
        payload = self._request("GET", f"/instance/connectionState/{instance_name}")
        return self._connection(instance_name, payload)

    def status(self, owner_id: str) -> WhatsAppConnection:
        instance_name = owner_instance_name(owner_id)
        if not self.configured:
            return WhatsAppConnection("unavailable", instance_name)
        try:
            connection = self._status(instance_name)
        except EvolutionServiceError as error:
            if "404" in str(error):
                return WhatsAppConnection("disconnected", instance_name)
            raise
        if connection.status == "connected":
            with self._lock:
                self._reconnect_after.pop(instance_name, None)
            return connection

        now = time.monotonic()
        with self._lock:
            retry_after = self._reconnect_after.get(instance_name, 0)
            if now < retry_after:
                return WhatsAppConnection(
                    "connecting", instance_name, connection.phone, connection.profile_name,
                )
            self._reconnect_after[instance_name] = now + 30
        try:
            payload = self._request("GET", f"/instance/connect/{instance_name}")
            recovered = self._connection(instance_name, payload, include_qr=True)
            if recovered.status == "connected":
                with self._lock:
                    self._reconnect_after.pop(instance_name, None)
                return recovered
            return WhatsAppConnection(
                "connecting", instance_name, recovered.phone, recovered.profile_name,
                recovered.qr_base64, recovered.pairing_code,
            )
        except EvolutionServiceError:
            # La consulta de estado sigue siendo válida. El próximo poll volverá
            # a intentar sin convertir una desconexión temporal en un error 503.
            return WhatsAppConnection(
                "connecting", instance_name, connection.phone, connection.profile_name,
            )

    def connect(self, owner_id: str) -> WhatsAppConnection:
        instance_name = owner_instance_name(owner_id)
        try:
            current = self._status(instance_name)
        except EvolutionServiceError as error:
            if "404" not in str(error):
                raise
            current = WhatsAppConnection("disconnected", instance_name)
        if current.status == "connected":
            return current
        if current.status == "disconnected":
            try:
                self._request("POST", "/instance/create", {
                    "instanceName": instance_name,
                    "integration": "WHATSAPP-BAILEYS",
                    "qrcode": True,
                    "syncFullHistory": False,
                    "readMessages": False,
                    "readStatus": False,
                })
            except EvolutionServiceError as error:
                if "403" not in str(error) and "409" not in str(error):
                    raise
        payload = self._request("GET", f"/instance/connect/{instance_name}")
        connection = self._connection(instance_name, payload, include_qr=True)
        return WhatsAppConnection(
            "connecting" if connection.status != "connected" else "connected",
            connection.instance_name,
            connection.phone,
            connection.profile_name,
            connection.qr_base64,
            connection.pairing_code,
        )

    def disconnect(self, owner_id: str) -> WhatsAppConnection:
        instance_name = owner_instance_name(owner_id)
        if self.configured:
            try:
                self._request("DELETE", f"/instance/logout/{instance_name}")
            except EvolutionServiceError as error:
                if "404" not in str(error):
                    raise
            try:
                self._request("DELETE", f"/instance/delete/{instance_name}")
            except EvolutionServiceError as error:
                if "404" not in str(error):
                    raise
        with self._lock:
            self._reconnect_after.pop(instance_name, None)
        return WhatsAppConnection("disconnected", instance_name)


evolution_service = EvolutionService()
