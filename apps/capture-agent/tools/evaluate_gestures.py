#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from inference.arms_up import ArmsUpGate, GestureRearmLatch, WristLiftTracker  # noqa: E402
from inference.evaluation import GestureWindow, evaluate_events  # noqa: E402
from inference.yolo_pose import YoloPoseDetector  # noqa: E402


def detect_events(video: Path, config: dict[str, object]) -> tuple[list[float], float]:
    fps = 5.0
    detector = YoloPoseDetector(
        model_name=str(config.get("model", "yolo26n-pose.pt")),
        device=str(config.get("device", "cpu")),
        image_size=int(config.get("image_size", 640)),
        person_confidence=float(config.get("person_confidence", 0.30)),
        keypoint_confidence=float(config.get("keypoint_confidence", 0.35)),
        rotation_degrees=int(config.get("rotation_degrees", 0)),
        roi=tuple(config.get("roi", [0.0, 0.0, 1.0, 1.0])),
        min_person_height_ratio=float(config.get("min_person_height_ratio", 0.06)),
    )
    gates: dict[int, ArmsUpGate] = {}
    wrist_lifts = WristLiftTracker(
        float(config.get("minimum_wrist_lift_ratio", 0.15)),
        float(config.get("minimum_local_motion", 0.10)),
    )
    rearm_latch = GestureRearmLatch(
        float(config.get("cooldown_seconds", 15.0)),
        float(config.get("release_seconds", 1.5)),
    )
    events: list[float] = []
    stop = threading.Event()
    frame_index = 0
    for frame in detector.stream(str(video), stop):
        timestamp = frame_index / fps
        frame_index += 1
        candidates: list[float] = []
        qualifying_raised = False
        for person in frame.persons:
            gate = gates.setdefault(
                person.track_id,
                ArmsUpGate(
                    hold_seconds=float(config.get("hold_seconds", 0.8)),
                    cooldown_seconds=0.0,
                    max_positive_gap_seconds=float(config.get("max_gap_seconds", 0.9)),
                ),
            )
            qualified = wrist_lifts.update(
                person.track_id,
                person.raised,
                person.left_wrist,
                person.right_wrist,
                person.body_height_ratio,
                person.local_motion_score,
                timestamp,
            )
            qualifying_raised = qualifying_raised or qualified
            confidence = gate.update(qualified, person.confidence, timestamp)
            if confidence is not None:
                candidates.append(confidence)
        if rearm_latch.update(qualifying_raised, bool(candidates), timestamp):
            events.append(timestamp)
    return events, frame_index / fps


def main() -> int:
    parser = argparse.ArgumentParser(description="Evalúa el detector de brazos sobre videos etiquetados.")
    parser.add_argument("manifest", type=Path, help="JSON con videos, ventanas de gesto y configuración opcional")
    args = parser.parse_args()
    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    base = args.manifest.resolve().parent
    config = dict(payload.get("detector", {}))
    reports = []
    all_expected: list[GestureWindow] = []
    all_predictions: list[float] = []
    total_duration = 0.0
    offset = 0.0
    for item in payload.get("videos", []):
        video = (base / str(item["path"])).resolve()
        predicted, duration = detect_events(video, config)
        expected = [GestureWindow(float(value["start"]), float(value["end"])) for value in item.get("gestures", [])]
        metrics = evaluate_events(expected, predicted, duration)
        reports.append({"video": str(video), "predicted_seconds": predicted, "metrics": metrics.as_dict()})
        all_expected.extend(GestureWindow(value.start + offset, value.end + offset) for value in expected)
        all_predictions.extend(value + offset for value in predicted)
        total_duration += duration
        offset += duration
    total = evaluate_events(all_expected, all_predictions, total_duration)
    print(json.dumps({"summary": total.as_dict(), "videos": reports}, indent=2))
    return 0 if total.recall >= 0.99 and total.false_positives_per_hour <= 0.1 else 2


if __name__ == "__main__":
    raise SystemExit(main())
