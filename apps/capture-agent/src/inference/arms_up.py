from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from statistics import median


LEFT_SHOULDER = 5
RIGHT_SHOULDER = 6
LEFT_ELBOW = 7
RIGHT_ELBOW = 8
LEFT_WRIST = 9
RIGHT_WRIST = 10
LEFT_HIP = 11
RIGHT_HIP = 12


@dataclass(frozen=True)
class PoseAssessment:
    raised: bool
    confidence: float
    center: tuple[float, float] | None = None
    body_height_ratio: float = 0.0
    inside_roi: bool = True
    left_wrist: tuple[float, float] | None = None
    right_wrist: tuple[float, float] | None = None
    wrist_spread_ratio: float = 0.0


def assess_arms_up(
    keypoints: list[list[float]] | tuple[tuple[float, ...], ...],
    min_keypoint_confidence: float = 0.35,
    *,
    frame_size: tuple[int, int] | None = None,
    roi: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0),
    min_person_height_ratio: float = 0.0,
    min_wrist_spread_ratio: float = 0.45,
) -> PoseAssessment:
    """Evaluate one COCO-17 pose using body-relative geometry.

    The rule intentionally uses shoulders, elbows and wrists. Checking wrists
    alone accepted poses with both hands barely above shoulder height and made
    the result too sensitive to one noisy keypoint. ROI and minimum-size gates
    are camera-relative, so the same configuration works at different
    resolutions.
    """
    if len(keypoints) <= RIGHT_WRIST:
        return PoseAssessment(False, 0.0)

    required = [
        keypoints[LEFT_SHOULDER],
        keypoints[RIGHT_SHOULDER],
        keypoints[LEFT_ELBOW],
        keypoints[RIGHT_ELBOW],
        keypoints[LEFT_WRIST],
        keypoints[RIGHT_WRIST],
    ]
    if any(len(point) < 2 for point in required):
        return PoseAssessment(False, 0.0)

    confidences = [float(point[2]) if len(point) > 2 else 1.0 for point in required]
    confidence = min(confidences)
    if confidence < min_keypoint_confidence:
        return PoseAssessment(False, confidence)

    left_shoulder, right_shoulder, left_elbow, right_elbow, left_wrist, right_wrist = required
    shoulder_span = abs(float(left_shoulder[0]) - float(right_shoulder[0]))
    shoulder_mid_y = (float(left_shoulder[1]) + float(right_shoulder[1])) / 2
    hip_points = [keypoints[index] for index in (LEFT_HIP, RIGHT_HIP) if len(keypoints) > index]
    visible_hips = [point for point in hip_points if len(point) > 2 and float(point[2]) >= min_keypoint_confidence]
    torso_height = abs(shoulder_mid_y - sum(float(point[1]) for point in visible_hips) / len(visible_hips)) if visible_hips else shoulder_span * 1.35
    body_scale = max(shoulder_span, torso_height, 12.0)
    vertical_margin = max(3.0, body_scale * 0.08)
    wrist_spread_ratio = abs(float(left_wrist[0]) - float(right_wrist[0])) / body_scale

    visible = [
        point for point in keypoints
        if len(point) >= 2 and (len(point) < 3 or float(point[2]) >= min_keypoint_confidence)
    ]
    center: tuple[float, float] | None = None
    body_height_ratio = 0.0
    inside_roi = True
    normalized_left_wrist: tuple[float, float] | None = None
    normalized_right_wrist: tuple[float, float] | None = None
    if visible and frame_size:
        frame_width, frame_height = frame_size
        xs = [float(point[0]) for point in visible]
        ys = [float(point[1]) for point in visible]
        center = ((min(xs) + max(xs)) / 2 / max(frame_width, 1), (min(ys) + max(ys)) / 2 / max(frame_height, 1))
        body_height_ratio = (max(ys) - min(ys)) / max(frame_height, 1)
        left, top, right, bottom = roi
        inside_roi = left <= center[0] <= right and top <= center[1] <= bottom
        normalized_left_wrist = (
            float(left_wrist[0]) / max(frame_width, 1),
            float(left_wrist[1]) / max(frame_height, 1),
        )
        normalized_right_wrist = (
            float(right_wrist[0]) / max(frame_width, 1),
            float(right_wrist[1]) / max(frame_height, 1),
        )

    raised = (
        float(left_wrist[1]) < float(left_shoulder[1]) - vertical_margin
        and float(right_wrist[1]) < float(right_shoulder[1]) - vertical_margin
        and float(left_elbow[1]) < float(left_shoulder[1]) + body_scale * 0.22
        and float(right_elbow[1]) < float(right_shoulder[1]) + body_scale * 0.22
        and float(left_wrist[1]) < float(left_elbow[1]) - body_scale * 0.05
        and float(right_wrist[1]) < float(right_elbow[1]) - body_scale * 0.05
        # A deliberate Vivoo gesture is a visible V. During smashes both hands
        # can rise briefly, but they normally converge around the racket.
        and wrist_spread_ratio >= min_wrist_spread_ratio
        and inside_roi
        and body_height_ratio >= min_person_height_ratio
    )
    return PoseAssessment(
        raised,
        confidence,
        center,
        body_height_ratio,
        inside_roi,
        normalized_left_wrist,
        normalized_right_wrist,
        wrist_spread_ratio,
    )


class WristLiftTracker:
    """Require upward movement from both wrists before accepting a held pose."""

    def __init__(
        self,
        minimum_lift_ratio: float = 0.15,
        minimum_local_motion: float = 0.10,
        window_seconds: float = 3.0,
    ) -> None:
        self.minimum_lift_ratio = max(0.0, minimum_lift_ratio)
        self.minimum_local_motion = max(0.0, minimum_local_motion)
        self.window_seconds = max(0.5, window_seconds)
        self._history: dict[int, deque[tuple[float, tuple[float, float], tuple[float, float]]]] = {}
        self._qualified: set[int] = set()

    def update(
        self,
        track_id: int,
        raised: bool,
        left_wrist: tuple[float, float] | None,
        right_wrist: tuple[float, float] | None,
        body_height_ratio: float,
        local_motion_score: float,
        observed_at: float,
    ) -> bool:
        if not raised:
            self._qualified.discard(track_id)
        if left_wrist is None or right_wrist is None:
            return raised and track_id in self._qualified

        history = self._history.setdefault(track_id, deque())
        cutoff = observed_at - self.window_seconds
        while history and history[0][0] < cutoff:
            history.popleft()
        lift = max(
            (
                min(previous_left[1] - left_wrist[1], previous_right[1] - right_wrist[1])
                for _, previous_left, previous_right in history
            ),
            default=0.0,
        )
        history.append((observed_at, left_wrist, right_wrist))
        relative_lift = lift / max(body_height_ratio, 0.1)
        if (
            raised
            and relative_lift >= self.minimum_lift_ratio
            and local_motion_score >= self.minimum_local_motion
        ):
            self._qualified.add(track_id)
        return raised and track_id in self._qualified

    def remove(self, track_id: int) -> None:
        self._history.pop(track_id, None)
        self._qualified.discard(track_id)


class ArmsUpGate:
    """Require a sustained gesture and one release before another trigger."""

    def __init__(
        self,
        hold_seconds: float = 0.8,
        cooldown_seconds: float = 15.0,
        release_seconds: float = 0.45,
        max_positive_gap_seconds: float = 0.35,
    ) -> None:
        self.hold_seconds = max(0.1, hold_seconds)
        self.cooldown_seconds = max(0.0, cooldown_seconds)
        self.release_seconds = max(0.1, release_seconds)
        self.max_positive_gap_seconds = max(0.1, max_positive_gap_seconds)
        self._raised_since: float | None = None
        self._last_positive_at: float | None = None
        self._released_since: float | None = None
        self._last_trigger_at: float | None = None
        self._armed = True
        self._positive_confidences: list[float] = []

    def update(self, raised: bool, confidence: float, observed_at: float) -> float | None:
        if not raised:
            self._raised_since = None
            self._last_positive_at = None
            self._positive_confidences.clear()
            if self._released_since is None:
                self._released_since = observed_at
            if observed_at - self._released_since >= self.release_seconds:
                self._armed = True
            return None

        self._released_since = None
        if (
            self._last_positive_at is None
            or observed_at - self._last_positive_at > self.max_positive_gap_seconds
        ):
            self._raised_since = observed_at
            self._positive_confidences.clear()
        self._last_positive_at = observed_at
        self._positive_confidences.append(confidence)
        self._positive_confidences = self._positive_confidences[-30:]

        if not self._armed or self._raised_since is None:
            return None
        if observed_at - self._raised_since < self.hold_seconds:
            return None
        if (
            self._last_trigger_at is not None
            and observed_at - self._last_trigger_at < self.cooldown_seconds
        ):
            return None

        self._armed = False
        self._last_trigger_at = observed_at
        return float(median(self._positive_confidences))


class GestureRearmLatch:
    """Block another event until the whole frame has returned to a neutral pose.

    Per-person tracking IDs can change while somebody keeps their arms raised.
    This frame-level latch prevents a new tracker from treating that same held
    pose as a fresh gesture. A real release starts a new gesture cycle
    immediately: a fixed cooldown must never hide a second intentional gesture.

    ``cooldown_seconds`` remains in the signature for compatibility with older
    agent configurations. Duplicate suppression is now driven by the release,
    which is both safer and easier for players to understand.
    """

    def __init__(self, cooldown_seconds: float = 15.0, release_seconds: float = 1.5) -> None:
        self.cooldown_seconds = max(0.0, cooldown_seconds)
        self.release_seconds = max(0.1, release_seconds)
        self._armed = True
        self._released_since: float | None = None
        self._last_trigger_at: float | None = None

    def update(self, any_raised: bool, has_candidate: bool, observed_at: float) -> bool:
        if not any_raised:
            if self._released_since is None:
                self._released_since = observed_at
            if observed_at - self._released_since >= self.release_seconds:
                self._armed = True
            return False

        self._released_since = None
        if not has_candidate or not self._armed:
            return False
        self._armed = False
        self._last_trigger_at = observed_at
        return True
