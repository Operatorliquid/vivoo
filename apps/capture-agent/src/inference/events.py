from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4


@dataclass(frozen=True)
class NormalizedCaptureEvent:
    source_id: str
    event_type: str
    occurred_at: datetime
    confidence: float | None = None
    buffer_start_at: datetime | None = None
    buffer_end_at: datetime | None = None
    source_storage_key: str | None = None


def manual_event(occurred_at: datetime) -> NormalizedCaptureEvent:
    return NormalizedCaptureEvent(
        source_id=f"manual-{uuid4()}",
        event_type="manual",
        occurred_at=occurred_at,
    )


def physical_button_event(device_id: str, event_id: str, occurred_at: datetime) -> NormalizedCaptureEvent:
    """Normalize a signed ESP32 press into the same event contract as a manual click."""
    return NormalizedCaptureEvent(
        source_id=f"button-{device_id}-{event_id}",
        event_type="physical_button",
        occurred_at=occurred_at,
    )


def gesture_event(occurred_at: datetime, confidence: float, threshold: float = 0.72) -> NormalizedCaptureEvent | None:
    if confidence < threshold:
        return None
    return NormalizedCaptureEvent(
        source_id=f"gesture-{uuid4()}",
        event_type="gesture",
        occurred_at=occurred_at,
        confidence=confidence,
    )
