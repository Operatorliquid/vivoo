from inference.evaluation import GestureWindow, evaluate_events


def test_evaluation_reports_recall_false_positives_and_latency() -> None:
    metrics = evaluate_events(
        [GestureWindow(10.0, 11.0), GestureWindow(30.0, 31.0)],
        [10.8, 22.0],
        video_duration_seconds=3600,
    )
    assert metrics.detected == 1
    assert metrics.missed == 1
    assert metrics.false_positives == 1
    assert metrics.recall == 0.5
    assert metrics.false_positives_per_hour == 1.0
    assert metrics.p95_latency_seconds == 0.8


def test_empty_negative_video_passes_without_false_positives() -> None:
    metrics = evaluate_events([], [], video_duration_seconds=600)
    assert metrics.recall == 1.0
    assert metrics.false_positives_per_hour == 0.0
