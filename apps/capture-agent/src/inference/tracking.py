from __future__ import annotations

from dataclasses import dataclass
from math import hypot


@dataclass
class _Track:
    center: tuple[float, float]
    velocity: tuple[float, float] = (0.0, 0.0)
    missed: int = 0


class CentroidTracker:
    """Small deterministic tracker for pose detections in a fixed camera.

    IDs are associated by predicted normalized position. It avoids coupling the
    gesture state to list order, which changes whenever players overlap or one
    person briefly disappears.
    """

    def __init__(self, max_distance: float = 0.18, max_missed_frames: int = 8) -> None:
        self.max_distance = max(0.02, max_distance)
        self.max_missed_frames = max(1, max_missed_frames)
        self._tracks: dict[int, _Track] = {}
        self._next_id = 1

    def reset(self) -> None:
        self._tracks.clear()
        self._next_id = 1

    def update(self, centers: list[tuple[float, float]]) -> list[int]:
        assignments: list[int | None] = [None] * len(centers)
        available_tracks = set(self._tracks)
        candidates: list[tuple[float, int, int]] = []
        for detection_index, center in enumerate(centers):
            for track_id, track in self._tracks.items():
                predicted = (track.center[0] + track.velocity[0], track.center[1] + track.velocity[1])
                distance = hypot(center[0] - predicted[0], center[1] - predicted[1])
                if distance <= self.max_distance:
                    candidates.append((distance, detection_index, track_id))

        used_detections: set[int] = set()
        for _, detection_index, track_id in sorted(candidates):
            if detection_index in used_detections or track_id not in available_tracks:
                continue
            assignments[detection_index] = track_id
            used_detections.add(detection_index)
            available_tracks.remove(track_id)

        for track_id, track in list(self._tracks.items()):
            if track_id in assignments:
                detection_index = assignments.index(track_id)
                next_center = centers[detection_index]
                track.velocity = (next_center[0] - track.center[0], next_center[1] - track.center[1])
                track.center = next_center
                track.missed = 0
            else:
                track.missed += 1
                if track.missed > self.max_missed_frames:
                    del self._tracks[track_id]

        for detection_index, assignment in enumerate(assignments):
            if assignment is not None:
                continue
            track_id = self._next_id
            self._next_id += 1
            self._tracks[track_id] = _Track(centers[detection_index])
            assignments[detection_index] = track_id

        return [int(value) for value in assignments]
