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
    """Small adapter for Evolution API's sendMedia endpoint."""

    def __init__(self, config: EvolutionConfig, opener: Callable = urlopen, max_retries: int = 3, sleeper: Callable[[float], None] = time.sleep) -> None:
        self.config = config
        self._opener = opener
        self.max_retries = max(0, max_retries)
        self._sleep = sleeper

    def send_video(self, phone_e164: str, media_url: str, caption: str, file_name: str = "vivoo-highlight.mp4", instance: str | None = None) -> dict:
        if not self.config.enabled:
            raise EvolutionApiError("Evolution API está desactivada")
        if not self.config.base_url or not self.config.api_key:
            raise EvolutionApiError("Evolution API no está configurada")
        payload = {
            "number": phone_e164,
            "mediatype": "video",
            "mimetype": "video/mp4",
            "caption": caption,
            "media": media_url,
            "fileName": file_name,
        }
        request = Request(
            f"{self.config.base_url.rstrip('/')}/message/sendMedia/{instance or self.config.instance}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "apikey": self.config.api_key},
            method="POST",
        )
        for attempt in range(self.max_retries + 1):
            try:
                with self._opener(request, timeout=30) as response:
                    body = response.read()
                    return json.loads(body.decode("utf-8")) if body else {"status": "accepted"}
            except HTTPError as error:
                detail = error.read().decode("utf-8", errors="replace")[:240]
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
