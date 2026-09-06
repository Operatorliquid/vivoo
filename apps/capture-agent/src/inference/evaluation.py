from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class GestureWindow:
    start: float
    end: float


@dataclass(frozen=True)
class EvaluationMetrics:
    expected: int
    detected: int
    missed: int
    false_positives: int
    recall: float
    false_positives_per_hour: float
    median_latency_seconds: float | None
    p95_latency_seconds: float | None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def evaluate_events(
    expected: list[GestureWindow],
    predicted_seconds: list[float],
    video_duration_seconds: float,
    *,
    allowed_latency_seconds: float = 2.0,
) -> EvaluationMetrics:
    unmatched = set(range(len(predicted_seconds)))
    latencies: list[float] = []
    for window in sorted(expected, key=lambda item: item.start):
        match = next(
            (
                index for index in sorted(unmatched, key=lambda item: predicted_seconds[item])
                if window.start <= predicted_seconds[index] <= window.end + allowed_latency_seconds
            ),
            None,
        )
        if match is None:
            continue
        unmatched.remove(match)
        latencies.append(round(max(0.0, predicted_seconds[match] - window.start), 3))

    detected = len(latencies)
    missed = max(0, len(expected) - detected)
    false_positives = len(unmatched)
    hours = max(video_duration_seconds / 3600, 1 / 3600)
    sorted_latencies = sorted(latencies)
    p95_index = max(0, min(len(sorted_latencies) - 1, int(round(0.95 * (len(sorted_latencies) - 1))))) if sorted_latencies else 0
    median_latency = sorted_latencies[len(sorted_latencies) // 2] if sorted_latencies else None
    return EvaluationMetrics(
        expected=len(expected),
        detected=detected,
        missed=missed,
        false_positives=false_positives,
        recall=detected / len(expected) if expected else 1.0,
        false_positives_per_hour=false_positives / hours,
        median_latency_seconds=median_latency,
        p95_latency_seconds=sorted_latencies[p95_index] if sorted_latencies else None,
    )
