from inference.tracking import CentroidTracker


def test_tracker_keeps_ids_when_detection_order_changes() -> None:
    tracker = CentroidTracker(max_distance=0.25)
    first = tracker.update([(0.2, 0.5), (0.8, 0.5)])
    second = tracker.update([(0.78, 0.5), (0.22, 0.5)])
    assert second == [first[1], first[0]]


def test_tracker_survives_short_occlusion_and_expires_stale_tracks() -> None:
    tracker = CentroidTracker(max_distance=0.25, max_missed_frames=2)
    first_id = tracker.update([(0.4, 0.4)])[0]
    tracker.update([])
    assert tracker.update([(0.42, 0.4)])[0] == first_id
    tracker.update([])
    tracker.update([])
    tracker.update([])
    assert tracker.update([(0.42, 0.4)])[0] != first_id
