from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from buffer.rolling_buffer import MediaSegment, RollingBuffer
from inference.events import gesture_event, manual_event


BASE = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)


def segment(name: str, start: int, end: int) -> MediaSegment:
    return MediaSegment(Path(name), BASE + timedelta(seconds=start), BASE + timedelta(seconds=end))


def test_buffer_keeps_safety_margin_and_returns_actual_window() -> None:
    buffer = RollingBuffer(retention_seconds=45)
    buffer.add_segment(segment("00.mp4", 0, 10))
    buffer.add_segment(segment("01.mp4", 10, 20))
    buffer.add_segment(segment("02.mp4", 20, 30))
    window = buffer.window_before(BASE + timedelta(seconds=30))
    assert window is not None
    assert window.start_at == BASE
    assert window.end_at == BASE + timedelta(seconds=30)
    assert window.duration_seconds == 30


def test_buffer_prunes_only_segments_outside_retention() -> None:
    buffer = RollingBuffer(retention_seconds=45)
    removed = buffer.add_segment(segment("old.mp4", 0, 10))
    assert removed == ()
    removed = buffer.add_segment(segment("new.mp4", 50, 60))
    assert [item.path.name for item in removed] == ["old.mp4"]
    assert [item.path.name for item in buffer.segments] == ["new.mp4"]


def test_event_normalization_keeps_manual_and_filters_low_confidence_gestures() -> None:
    manual = manual_event(BASE)
    assert manual.event_type == "manual"
    assert manual.source_id.startswith("manual-")
    assert gesture_event(BASE, 0.5) is None
    gesture = gesture_event(BASE, 0.9)
    assert gesture is not None
    assert gesture.event_type == "gesture"
    assert gesture.confidence == 0.9


def test_buffer_rejects_short_retention_and_invalid_segments() -> None:
    with pytest.raises(ValueError):
        RollingBuffer(retention_seconds=29)
    with pytest.raises(ValueError):
        RollingBuffer().add_segment(segment("broken.mp4", 20, 20))
