from __future__ import annotations

from collections.abc import Callable
from collections import deque
from datetime import datetime, timezone
import threading
import time

from inference.arms_up import ArmsUpGate, GestureRearmLatch, WristLiftTracker
from inference.yolo_pose import PoseDetectorUnavailable, YoloPoseDetector


class GestureMonitor:
    def __init__(
        self,
        detector: YoloPoseDetector,
        on_gesture: Callable[[float, datetime], None],
        on_status: Callable[[str, str], None],
        on_observation: Callable[[bool, float, int, int, float, float, datetime], None] | None = None,
        hold_seconds: float = 0.8,
        cooldown_seconds: float = 15.0,
        release_seconds: float = 1.5,
        minimum_wrist_lift_ratio: float = 0.15,
        minimum_local_motion: float = 0.10,
        max_positive_gap_seconds: float = 0.9,
    ) -> None:
        self.detector = detector
        self.on_gesture = on_gesture
        self.on_status = on_status
        self.on_observation = on_observation
        self.hold_seconds = hold_seconds
        self.cooldown_seconds = cooldown_seconds
        self.release_seconds = release_seconds
        self.minimum_wrist_lift_ratio = minimum_wrist_lift_ratio
        self.minimum_local_motion = minimum_local_motion
        self.max_positive_gap_seconds = max_positive_gap_seconds
        self._gates: dict[int, ArmsUpGate] = {}
        self._track_seen_at: dict[int, float] = {}
        self._rearm_latch = GestureRearmLatch(cooldown_seconds, release_seconds)
        self._wrist_lifts = WristLiftTracker(minimum_wrist_lift_ratio, minimum_local_motion)
        self._frame_times: deque[float] = deque(maxlen=60)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._source = ""
        self._last_status: tuple[str, str] | None = None
        self._last_observation_at = 0.0

    def _set_status(self, status: str, detail: str) -> None:
        value = (status, detail)
        if value == self._last_status:
            return
        self._last_status = value
        self.on_status(status, detail)

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    @property
    def source(self) -> str:
        return self._source

    def start(self, source: str) -> None:
        if self.running and self._source == source:
            return
        self.stop()
        self._source = source
        self._last_status = None
        self._gates.clear()
        self._track_seen_at.clear()
        self._rearm_latch = GestureRearmLatch(self.cooldown_seconds, self.release_seconds)
        self._wrist_lifts = WristLiftTracker(
            self.minimum_wrist_lift_ratio,
            self.minimum_local_motion,
        )
        self._frame_times.clear()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="courtvision-pose", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.5)
        self._thread = None

    def _run(self) -> None:
        self._set_status("loading", "Cargando detector de pose")
        while not self._stop.is_set():
            try:
                for frame in self.detector.stream(self._source, self._stop):
                    if self._stop.is_set():
                        return
                    now = time.monotonic()
                    self._frame_times.append(now)
                    fps = 0.0
                    if len(self._frame_times) > 1:
                        elapsed = self._frame_times[-1] - self._frame_times[0]
                        fps = (len(self._frame_times) - 1) / elapsed if elapsed > 0 else 0.0
                    if len(self._frame_times) >= 10 and fps < 2.5:
                        self._set_status("degraded", f"Detector lento · {fps:.1f} FPS")
                    else:
                        self._set_status("running", "Analizando gesto de brazos")
                    if self.on_observation is not None and now - self._last_observation_at >= 1.0:
                        self._last_observation_at = now
                        self.on_observation(
                            frame.raised,
                            frame.confidence,
                            frame.people,
                            frame.tracked_people,
                            fps,
                            frame.inference_ms,
                            datetime.now(timezone.utc),
                        )

                    candidates: list[float] = []
                    qualifying_raised = False
                    for person in frame.persons:
                        gate = self._gates.setdefault(
                            person.track_id,
                            ArmsUpGate(
                                self.hold_seconds,
                                0.0,
                                max_positive_gap_seconds=self.max_positive_gap_seconds,
                            ),
                        )
                        self._track_seen_at[person.track_id] = now
                        qualified = self._wrist_lifts.update(
                            person.track_id,
                            person.raised,
                            person.left_wrist,
                            person.right_wrist,
                            person.body_height_ratio,
                            person.local_motion_score,
                            now,
                        )
                        qualifying_raised = qualifying_raised or qualified
                        confidence = gate.update(qualified, person.confidence, now)
                        if confidence is not None:
                            candidates.append(confidence)
                    for track_id, last_seen in list(self._track_seen_at.items()):
                        if now - last_seen > 3.0:
                            self._track_seen_at.pop(track_id, None)
                            self._gates.pop(track_id, None)
                            self._wrist_lifts.remove(track_id)

                    if self._rearm_latch.update(qualifying_raised, bool(candidates), now):
                        self.on_gesture(max(candidates), datetime.now(timezone.utc))
                if not self._stop.wait(2.0):
                    self._set_status("reconnecting", "Reconectando el detector a la cámara")
            except PoseDetectorUnavailable as error:
                self._set_status("unavailable", str(error))
                return
            except Exception as error:  # the stream must recover without killing the agent
                self._set_status("error", f"Detector de pose: {error}")
                if self._stop.wait(3.0):
                    return
