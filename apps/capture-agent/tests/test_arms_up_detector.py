from inference.arms_up import ArmsUpGate, GestureRearmLatch, WristLiftTracker, assess_arms_up


def pose(left_wrist_y: float, right_wrist_y: float, confidence: float = 0.9):
    points = [[0.0, 0.0, confidence] for _ in range(17)]
    points[0] = [150.0, 120.0, confidence]
    points[5] = [100.0, 200.0, confidence]
    points[6] = [200.0, 200.0, confidence]
    points[7] = [105.0, 180.0, confidence]
    points[8] = [195.0, 180.0, confidence]
    points[9] = [100.0, left_wrist_y, confidence]
    points[10] = [200.0, right_wrist_y, confidence]
    points[11] = [115.0, 300.0, confidence]
    points[12] = [185.0, 300.0, confidence]
    points[15] = [120.0, 420.0, confidence]
    points[16] = [180.0, 420.0, confidence]
    return points


def test_requires_both_wrists_above_the_shoulders() -> None:
    assert assess_arms_up(pose(160.0, 160.0)).raised is True
    assert assess_arms_up(pose(160.0, 230.0)).raised is False
    assert assess_arms_up(pose(230.0, 230.0)).raised is False


def test_rejects_low_confidence_keypoints() -> None:
    assessment = assess_arms_up(pose(150.0, 150.0, confidence=0.2))
    assert assessment.raised is False
    assert assessment.confidence == 0.2


def test_rejects_pose_outside_roi_or_too_small() -> None:
    outside = assess_arms_up(
        pose(150.0, 150.0),
        frame_size=(640, 480),
        roi=(0.4, 0.0, 1.0, 1.0),
        min_person_height_ratio=0.1,
    )
    assert outside.raised is False
    assert outside.inside_roi is False

    small = [[point[0] * 0.05, point[1] * 0.05, point[2]] for point in pose(150.0, 150.0)]
    assessment = assess_arms_up(small, frame_size=(640, 480), min_person_height_ratio=0.1)
    assert assessment.raised is False
    assert assessment.body_height_ratio < 0.1


def test_gate_requires_hold_release_and_cooldown() -> None:
    gate = ArmsUpGate(hold_seconds=0.8, cooldown_seconds=3.0, release_seconds=0.4)
    assert gate.update(True, 0.9, 0.0) is None
    assert gate.update(True, 0.9, 0.3) is None
    assert gate.update(True, 0.9, 0.6) is None
    assert gate.update(True, 0.9, 0.81) == 0.9
    assert gate.update(True, 0.9, 1.2) is None
    assert gate.update(False, 0.0, 1.3) is None
    assert gate.update(False, 0.0, 1.8) is None
    assert gate.update(True, 0.8, 3.9) is None
    assert gate.update(True, 0.8, 4.2) is None
    assert gate.update(True, 0.8, 4.5) is None
    assert gate.update(True, 0.8, 4.71) == 0.8


def test_gate_tolerates_a_dropped_frame_without_accepting_a_release() -> None:
    gate = ArmsUpGate(hold_seconds=0.8, cooldown_seconds=0.0, max_positive_gap_seconds=0.9)
    assert gate.update(True, 0.72, 0.0) is None
    assert gate.update(True, 0.84, 0.3) is None
    assert gate.update(True, 0.78, 0.85) == 0.78
    assert gate.update(False, 0.0, 1.0) is None
    assert gate.update(True, 0.9, 1.2) is None


def test_frame_latch_requires_a_real_release_even_when_tracker_changes() -> None:
    latch = GestureRearmLatch(cooldown_seconds=3.0, release_seconds=1.0)
    assert latch.update(True, True, 1.0) is True
    assert latch.update(True, True, 5.0) is False
    assert latch.update(False, False, 5.1) is False
    assert latch.update(True, True, 5.8) is False
    assert latch.update(False, False, 6.0) is False
    assert latch.update(False, False, 7.1) is False
    assert latch.update(True, True, 7.2) is True


def test_frame_latch_accepts_a_new_released_gesture_without_a_fixed_cooldown() -> None:
    latch = GestureRearmLatch(cooldown_seconds=15.0, release_seconds=0.75)
    assert latch.update(True, True, 1.0) is True
    assert latch.update(True, True, 1.4) is False
    assert latch.update(False, False, 1.5) is False
    assert latch.update(False, False, 2.3) is False
    assert latch.update(True, True, 2.4) is True


def test_wrist_lift_rejects_static_pose_and_accepts_two_arm_motion() -> None:
    tracker = WristLiftTracker(minimum_lift_ratio=0.15, minimum_local_motion=0.10, window_seconds=3.0)
    assert tracker.update(1, False, (0.4, 0.55), (0.6, 0.55), 0.5, 0.0, 0.0) is False
    assert tracker.update(1, True, (0.4, 0.54), (0.6, 0.54), 0.5, 0.01, 0.5) is False
    assert tracker.update(1, True, (0.4, 0.46), (0.6, 0.45), 0.5, 0.14, 1.0) is True
    assert tracker.update(1, True, (0.4, 0.46), (0.6, 0.45), 0.5, 0.0, 2.0) is True
    tracker.remove(1)
    assert tracker.update(1, True, (0.4, 0.46), (0.6, 0.45), 0.5, 0.14, 2.1) is False
