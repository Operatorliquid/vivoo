from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass(frozen=True)
class MediaSegment:
    path: Path
    start_at: datetime
    end_at: datetime

    @property
    def duration_seconds(self) -> float:
        return max(0.0, (self.end_at - self.start_at).total_seconds())


@dataclass(frozen=True)
class AvailableWindow:
    start_at: datetime
    end_at: datetime
    segments: tuple[MediaSegment, ...]

    @property
    def duration_seconds(self) -> float:
        return max(0.0, (self.end_at - self.start_at).total_seconds())


class RollingBuffer:
    """Bounded segment index kept on the club-side capture machine."""

    def __init__(self, retention_seconds: int = 45) -> None:
        if retention_seconds < 30:
            raise ValueError("retention_seconds must cover the 30-second highlight window")
        self.retention_seconds = retention_seconds
        self._segments: list[MediaSegment] = []

    @property
    def segments(self) -> tuple[MediaSegment, ...]:
        return tuple(self._segments)

    def add_segment(self, segment: MediaSegment) -> tuple[MediaSegment, ...]:
        if segment.end_at <= segment.start_at:
            raise ValueError("segment end_at must be after start_at")
        self._segments.append(segment)
        self._segments.sort(key=lambda item: item.start_at)
        cutoff = segment.end_at - timedelta(seconds=self.retention_seconds)
        removed = tuple(item for item in self._segments if item.end_at <= cutoff)
        self._segments = [item for item in self._segments if item.end_at > cutoff]
        return removed

    def window_before(self, occurred_at: datetime, duration_seconds: int = 30) -> AvailableWindow | None:
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        requested_start = occurred_at - timedelta(seconds=duration_seconds)
        selected = tuple(
            item for item in self._segments
            if item.end_at > requested_start and item.start_at < occurred_at
        )
        if not selected:
            return None
        actual_start = max(requested_start, selected[0].start_at)
        actual_end = min(occurred_at, selected[-1].end_at)
        return AvailableWindow(actual_start, actual_end, selected)

    def remove(self, segments: tuple[MediaSegment, ...]) -> None:
        paths = {segment.path for segment in segments}
        self._segments = [segment for segment in self._segments if segment.path not in paths]
