from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from inference.events import NormalizedCaptureEvent, physical_button_event


class ButtonEventError(ValueError):
    pass


@dataclass(frozen=True)
class ButtonPress:
    device_id: str
    event_id: str
    pressed_at: datetime


def _canonical(device_id: str, event_id: str, pressed_at: str) -> bytes:
    return f"{device_id}:{event_id}:{pressed_at}".encode("utf-8")


def signature_for(secret: str, device_id: str, event_id: str, pressed_at: str) -> str:
    return hmac.new(secret.encode("utf-8"), _canonical(device_id, event_id, pressed_at), hashlib.sha256).hexdigest()


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ButtonEventError("pressed_at must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ButtonEventError("pressed_at must include timezone")
    return parsed.astimezone(timezone.utc)


def parse_press(payload: dict[str, object], secret: str, now: datetime | None = None, max_clock_skew_seconds: int = 90) -> ButtonPress:
    device_id = str(payload.get("device_id", "")).strip()
    event_id = str(payload.get("event_id", "")).strip()
    pressed_at_raw = str(payload.get("pressed_at", "")).strip()
    provided_signature = str(payload.get("signature", "")).strip().lower()
    if len(device_id) < 2 or len(device_id) > 120 or len(event_id) < 2 or len(event_id) > 120:
        raise ButtonEventError("device_id and event_id are required")
    if not provided_signature:
        raise ButtonEventError("signature is required")
    expected = signature_for(secret, device_id, event_id, pressed_at_raw)
    if not hmac.compare_digest(provided_signature, expected):
        raise ButtonEventError("invalid button signature")
    pressed_at = _parse_timestamp(pressed_at_raw)
    reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if abs((reference - pressed_at).total_seconds()) > max_clock_skew_seconds:
        raise ButtonEventError("button timestamp is outside the accepted window")
    return ButtonPress(device_id, event_id, pressed_at)


class ButtonEventNormalizer:
    """Verifies ESP32 presses and prevents switch bounce from creating duplicate clips."""

    def __init__(self, secret: str, debounce_seconds: float = 1.5, clock: Callable[[], datetime] | None = None) -> None:
        self.secret = secret
        self.debounce = timedelta(seconds=debounce_seconds)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._seen_ids: set[tuple[str, str]] = set()
        self._last_press: dict[str, datetime] = {}

    def normalize(self, payload: dict[str, object]) -> NormalizedCaptureEvent | None:
        press = parse_press(payload, self.secret, self.clock())
        identity = (press.device_id, press.event_id)
        if identity in self._seen_ids:
            return None
        previous = self._last_press.get(press.device_id)
        self._seen_ids.add(identity)
        if previous and press.pressed_at - previous < self.debounce:
            return None
        self._last_press[press.device_id] = press.pressed_at
        return physical_button_event(press.device_id, press.event_id, press.pressed_at)


def parse_json_payload(body: bytes) -> dict[str, object]:
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ButtonEventError("invalid JSON payload") from error
    if not isinstance(value, dict):
        raise ButtonEventError("button payload must be an object")
    return value
