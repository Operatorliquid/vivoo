from datetime import datetime, timedelta, timezone
import json

import pytest

from button.protocol import ButtonEventError, ButtonEventNormalizer, signature_for
from button.server import ButtonEventReceiver


BASE = datetime(2026, 8, 12, 15, 0, tzinfo=timezone.utc)


def payload(event_id: str = "press-001", at: datetime = BASE, secret: str = "button-secret") -> dict[str, str]:
    pressed_at = at.isoformat().replace("+00:00", "Z")
    return {
        "device_id": "CV-BTN-01",
        "event_id": event_id,
        "pressed_at": pressed_at,
        "signature": signature_for(secret, "CV-BTN-01", event_id, pressed_at),
    }


def test_signed_press_becomes_physical_button_event() -> None:
    normalizer = ButtonEventNormalizer("button-secret", clock=lambda: BASE)
    event = normalizer.normalize(payload())
    assert event is not None
    assert event.event_type == "physical_button"
    assert event.source_id == "button-CV-BTN-01-press-001"


def test_invalid_signature_and_bounce_are_rejected() -> None:
    normalizer = ButtonEventNormalizer("button-secret", clock=lambda: BASE)
    invalid = payload()
    invalid["signature"] = "bad"
    with pytest.raises(ButtonEventError):
        normalizer.normalize(invalid)
    assert normalizer.normalize(payload()) is not None
    assert normalizer.normalize(payload("press-002", BASE + timedelta(seconds=1))) is None
    assert normalizer.normalize(payload("press-003", BASE + timedelta(seconds=2))) is not None


def test_receiver_only_emits_accepted_events() -> None:
    events = []
    receiver = ButtonEventReceiver("button-secret", events.append, ButtonEventNormalizer("button-secret", clock=lambda: BASE))
    response = receiver.receive(json.dumps(payload()).encode())
    assert response is not None
    assert len(events) == 1
