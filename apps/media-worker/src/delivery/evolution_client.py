from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class EvolutionApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class EvolutionConfig:
    base_url: str
    api_key: str
    instance: str
    enabled: bool = False


class EvolutionApiClient:
    """Evolution adapter that repairs persisted WhatsApp sessions before sending."""

    def __init__(self, config: EvolutionConfig, opener: Callable = urlopen, max_retries: int = 3, sleeper: Callable[[float], None] = time.sleep) -> None:
        self.config = config
        self._opener = opener
        self.max_retries = max(0, max_retries)
        self._sleep = sleeper

    def _request(self, method: str, path: str, payload: dict | None = None, *, timeout: int = 30) -> dict:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        for attempt in range(self.max_retries + 1):
            request = Request(
                f"{self.config.base_url.rstrip('/')}{path}",
                data=body,
                headers={"Accept": "application/json", "Content-Type": "application/json", "apikey": self.config.api_key},
                method=method,
            )
            try:
                with self._opener(request, timeout=timeout) as response:
                    raw = response.read()
                    return json.loads(raw.decode("utf-8")) if raw else {"status": "accepted"}
            except HTTPError as error:
                detail = error.read().decode("utf-8", errors="replace")[:240] if error.fp else ""
                retryable = error.code in {408, 429, 500, 502, 503, 504}
                if not retryable or attempt == self.max_retries:
                    suffix = f": {detail}" if detail else ""
                    raise EvolutionApiError(f"Evolution API devolvió {error.code}{suffix}") from error
            except OSError as error:
                if attempt == self.max_retries:
                    raise EvolutionApiError("Evolution API no está disponible") from error
            except json.JSONDecodeError as error:
                raise EvolutionApiError("Evolution API devolvió una respuesta inválida") from error
            self._sleep(min(0.5 * (2 ** attempt), 4))
        raise EvolutionApiError("Evolution API no está disponible")

    @staticmethod
    def _state(payload: dict) -> str:
        instance = payload.get("instance") if isinstance(payload.get("instance"), dict) else payload
        return str(instance.get("state") or instance.get("connectionStatus") or "close").lower()

    def ensure_connected(self, instance: str) -> None:
        try:
            state = self._state(self._request("GET", f"/instance/connectionState/{instance}", timeout=15))
        except EvolutionApiError as error:
            if "404" in str(error):
                raise EvolutionApiError("WhatsApp necesita volver a vincularse desde Configuración") from error
            raise
        if state == "open":
            return

        reconnect = self._request("GET", f"/instance/connect/{instance}", timeout=20)
        if self._state(reconnect) == "open":
            return
        if reconnect.get("base64") or reconnect.get("qrcode") or reconnect.get("pairingCode"):
            raise EvolutionApiError("WhatsApp necesita volver a escanear el QR desde Configuración")
        for delay in (1, 2, 4):
            self._sleep(delay)
            if self._state(self._request("GET", f"/instance/connectionState/{instance}", timeout=15)) == "open":
                return
        raise EvolutionApiError("WhatsApp sigue reconectándose; el envío se reintentará automáticamente")

    def send_video(self, phone_e164: str, media_url: str, caption: str, file_name: str = "vivoo-highlight.mp4", instance: str | None = None) -> dict:
        if not self.config.enabled:
            raise EvolutionApiError("Evolution API está desactivada")
        if not self.config.base_url or not self.config.api_key:
            raise EvolutionApiError("Evolution API no está configurada")
        instance_name = instance or self.config.instance
        self.ensure_connected(instance_name)
        payload = {
            "number": phone_e164,
            "mediatype": "video",
            "mimetype": "video/mp4",
            "caption": caption,
            "media": media_url,
            "fileName": file_name,
        }
        return self._request("POST", f"/message/sendMedia/{instance_name}", payload)
