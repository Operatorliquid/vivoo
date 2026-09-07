from __future__ import annotations

from collections.abc import Iterator
from collections import deque
from dataclasses import dataclass
import threading
import time

from camera.frames import stream_bgr_frames
from inference.arms_up import PoseAssessment, assess_arms_up
from inference.tracking import CentroidTracker


class PoseDetectorUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class PosePerson:
    track_id: int
    raised: bool
    confidence: float
    inside_roi: bool
    body_height_ratio: float
    left_wrist: tuple[float, float] | None = None
    right_wrist: tuple[float, float] | None = None
    local_motion_score: float = 0.0


@dataclass(frozen=True)
class PoseFrame:
    raised: bool
    confidence: float
    people: int
    tracked_people: int = 0
    inference_ms: float = 0.0
    persons: tuple[PosePerson, ...] = ()


class YoloPoseDetector:
    def __init__(
        self,
        model_name: str = "yolo26n-pose.pt",
        device: str = "cpu",
        image_size: int = 960,
        person_confidence: float = 0.30,
        keypoint_confidence: float = 0.35,
        rotation_degrees: int = 0,
        roi: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0),
        min_person_height_ratio: float = 0.06,
        min_wrist_spread_ratio: float = 0.45,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.image_size = image_size
        self.person_confidence = person_confidence
        self.keypoint_confidence = keypoint_confidence
        self.rotation_degrees = rotation_degrees
        self.roi = roi
        self.min_person_height_ratio = min_person_height_ratio
        self.min_wrist_spread_ratio = min_wrist_spread_ratio
        self._model = None
        self._tracker = CentroidTracker()

    def _load_model(self):
        if self._model is not None:
            return self._model
        try:
            from ultralytics import YOLO
        except ImportError as error:
            raise PoseDetectorUnavailable(
                "Falta instalar el paquete de visión: pip install '.[vision]'"
            ) from error
        self._model = YOLO(self.model_name)
        return self._model

    def stream(self, source: str, stop_event: threading.Event) -> Iterator[PoseFrame]:
        model = self._load_model()
        self._tracker.reset()
        frame_history: deque[object] = deque(maxlen=6)
        detector_width = max(640, self.image_size)
        detector_height = max(360, round(detector_width * 9 / 16))
        for frame in stream_bgr_frames(
            source,
            stop_event,
            width=detector_width,
            height=detector_height,
            rotation_degrees=self.rotation_degrees,
        ):
            if stop_event.is_set():
                break
            reference_frame = frame_history[0] if len(frame_history) == frame_history.maxlen else None
            frame_history.append(frame.copy())
            inference_started = time.perf_counter()
            results = model.predict(
                source=frame,
                imgsz=self.image_size,
                conf=self.person_confidence,
                device=self.device,
                verbose=False,
            )
            inference_ms = (time.perf_counter() - inference_started) * 1000
            if not results:
                self._tracker.update([])
                yield PoseFrame(False, 0.0, 0, inference_ms=inference_ms)
                continue
            result = results[0]
            keypoints = getattr(result, "keypoints", None)
            if keypoints is None or keypoints.data is None:
                self._tracker.update([])
                yield PoseFrame(False, 0.0, 0, inference_ms=inference_ms)
                continue
            people = keypoints.data.detach().cpu().tolist()
            frame_height, frame_width = frame.shape[:2]
            assessments: list[PoseAssessment] = [
                assess_arms_up(
                    person,
                    self.keypoint_confidence,
                    frame_size=(frame_width, frame_height),
                    roi=self.roi,
                    min_person_height_ratio=self.min_person_height_ratio,
                    min_wrist_spread_ratio=self.min_wrist_spread_ratio,
                )
                for person in people
            ]
            centered = [(index, assessment.center) for index, assessment in enumerate(assessments) if assessment.center is not None]
            track_ids = self._tracker.update([center for _, center in centered if center is not None])
            assigned = {assessment_index: track_id for (assessment_index, _), track_id in zip(centered, track_ids)}
            persons = tuple(
                PosePerson(
                    track_id=assigned[index],
                    raised=assessment.raised,
                    confidence=assessment.confidence,
                    inside_roi=assessment.inside_roi,
                    body_height_ratio=assessment.body_height_ratio,
                    left_wrist=assessment.left_wrist,
                    right_wrist=assessment.right_wrist,
                    local_motion_score=local_patch_motion(
                        frame,
                        reference_frame,
                        assessment.left_wrist,
                        assessment.right_wrist,
                    ),
                )
                for index, assessment in enumerate(assessments)
                if index in assigned
            )
            raised = [assessment for assessment in assessments if assessment.raised]
            best = max(raised, key=lambda item: item.confidence, default=None)
            yield PoseFrame(
                bool(best),
                best.confidence if best else 0.0,
                len(people),
                tracked_people=len(persons),
                inference_ms=inference_ms,
                persons=persons,
            )


def local_patch_motion(
    frame: object,
    reference_frame: object | None,
    left_wrist: tuple[float, float] | None,
    right_wrist: tuple[float, float] | None,
) -> float:
    """Measure real image change around both predicted wrists over about one second."""
    if reference_frame is None or left_wrist is None or right_wrist is None:
        return 0.0
    try:
        import numpy as np

        height, width = frame.shape[:2]
        radius = max(6, min(height, width) // 32)
        scores: list[float] = []
        for normalized_x, normalized_y in (left_wrist, right_wrist):
            x = int(normalized_x * width)
            y = int(normalized_y * height)
            left, right = max(0, x - radius), min(width, x + radius + 1)
            top, bottom = max(0, y - radius), min(height, y + radius + 1)
            if right <= left or bottom <= top:
                return 0.0
            current_patch = frame[top:bottom, left:right].astype(np.int16)
            previous_patch = reference_frame[top:bottom, left:right].astype(np.int16)
            scores.append(float(np.mean(np.abs(current_patch - previous_patch))) / 255.0)
        return min(scores, default=0.0)
    except (AttributeError, TypeError, ValueError):
        return 0.0
