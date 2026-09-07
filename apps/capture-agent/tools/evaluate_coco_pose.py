#!/usr/bin/env python3
"""Measure gesture candidates in COCO-17 pose annotations.

This benchmark intentionally treats every pose transition as if its image-motion
check had passed. It therefore reports a conservative upper bound for candidate
events, not the final false-positive rate of the video detector.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from inference.arms_up import ArmsUpGate, GestureRearmLatch, WristLiftTracker, assess_arms_up  # noqa: E402
from inference.tracking import CentroidTracker  # noqa: E402


def coco_keypoints(values: list[float]) -> list[list[float]]:
    if len(values) != 51:
        raise ValueError("Cada pose debe contener 17 keypoints COCO (51 valores)")
    return [
        [float(values[index]), float(values[index + 1]), min(1.0, float(values[index + 2]) / 2.0)]
        for index in range(0, len(values), 3)
    ]


def evaluate_file(path: Path, args: argparse.Namespace) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    images = {int(image["id"]): image for image in payload.get("images", [])}
    annotations: dict[int, list[list[list[float]]]] = defaultdict(list)
    for annotation in payload.get("annotations", []):
        try:
            annotations[int(annotation["image_id"])].append(coco_keypoints(annotation["keypoints"]))
        except (KeyError, TypeError, ValueError):
            continue

    sample_every = max(1, round(args.source_fps / args.sample_fps))
    tracker = CentroidTracker()
    wrist_lifts = WristLiftTracker(args.minimum_wrist_lift_ratio, 0.0)
    latch = GestureRearmLatch(0.0, args.release_seconds)
    gates: dict[int, ArmsUpGate] = {}
    last_seen: dict[int, float] = {}
    triggers: list[float] = []
    sampled_frames = 0
    assessed_poses = 0
    geometry_positive_frames = 0

    for image_id in sorted(images):
        if (image_id - 1) % sample_every:
            continue
        sampled_frames += 1
        observed_at = (image_id - 1) / args.source_fps
        image = images[image_id]
        frame_size = (int(image["width"]), int(image["height"]))
        assessments = [
            assess_arms_up(
                pose,
                args.keypoint_confidence,
                frame_size=frame_size,
                min_person_height_ratio=args.min_person_height_ratio,
                min_wrist_spread_ratio=args.min_wrist_spread_ratio,
            )
            for pose in annotations.get(image_id, [])
        ]
        assessed_poses += len(assessments)
        geometry_positive_frames += int(any(item.raised for item in assessments))

        centered = [(index, item.center) for index, item in enumerate(assessments) if item.center is not None]
        track_ids = tracker.update([center for _, center in centered if center is not None])
        assigned = {index: track_id for (index, _), track_id in zip(centered, track_ids)}
        candidates: list[float] = []
        any_qualified = False
        for index, assessment in enumerate(assessments):
            if index not in assigned:
                continue
            track_id = assigned[index]
            last_seen[track_id] = observed_at
            # Pixel patches are unavailable in annotation-only datasets. Passing
            # this gate produces the conservative upper bound documented above.
            qualified = wrist_lifts.update(
                track_id,
                assessment.raised,
                assessment.left_wrist,
                assessment.right_wrist,
                assessment.body_height_ratio,
                1.0,
                observed_at,
            )
            any_qualified = any_qualified or qualified
            confidence = gates.setdefault(
                track_id,
                ArmsUpGate(
                    args.hold_seconds,
                    0.0,
                    max_positive_gap_seconds=args.max_gap_seconds,
                ),
            ).update(qualified, assessment.confidence, observed_at)
            if confidence is not None:
                candidates.append(confidence)

        for track_id, seen_at in list(last_seen.items()):
            if observed_at - seen_at <= 3.0:
                continue
            last_seen.pop(track_id, None)
            gates.pop(track_id, None)
            wrist_lifts.remove(track_id)
        if latch.update(any_qualified, bool(candidates), observed_at):
            triggers.append(round(observed_at, 3))

    duration = len(images) / args.source_fps
    hours = max(duration / 3600.0, 1 / 3600.0)
    return {
        "file": str(path.resolve()),
        "frames": len(images),
        "sampled_frames": sampled_frames,
        "assessed_poses": assessed_poses,
        "duration_seconds": round(duration, 3),
        "geometry_positive_frames": geometry_positive_frames,
        "upper_bound_candidate_events": len(triggers),
        "upper_bound_candidates_per_hour": round(len(triggers) / hours, 3),
        "candidate_seconds": triggers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evalúa falsos candidatos sobre poses COCO-17")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--source-fps", type=float, default=30.0)
    parser.add_argument("--sample-fps", type=float, default=5.0)
    parser.add_argument("--keypoint-confidence", type=float, default=0.35)
    parser.add_argument("--min-person-height-ratio", type=float, default=0.06)
    parser.add_argument("--min-wrist-spread-ratio", type=float, default=0.45)
    parser.add_argument("--minimum-wrist-lift-ratio", type=float, default=0.15)
    parser.add_argument("--hold-seconds", type=float, default=1.2)
    parser.add_argument("--release-seconds", type=float, default=0.75)
    parser.add_argument("--max-gap-seconds", type=float, default=0.9)
    args = parser.parse_args()
    if args.source_fps <= 0 or args.sample_fps <= 0:
        parser.error("Los FPS deben ser mayores que cero")

    reports = [evaluate_file(path, args) for path in args.files]
    total_duration = sum(float(report["duration_seconds"]) for report in reports)
    total_candidates = sum(int(report["upper_bound_candidate_events"]) for report in reports)
    hours = max(total_duration / 3600.0, 1 / 3600.0)
    print(json.dumps({
        "method": "annotation_only_upper_bound",
        "configuration": {
            "source_fps": args.source_fps,
            "sample_fps": args.sample_fps,
            "hold_seconds": args.hold_seconds,
            "min_wrist_spread_ratio": args.min_wrist_spread_ratio,
        },
        "summary": {
            "duration_seconds": round(total_duration, 3),
            "upper_bound_candidate_events": total_candidates,
            "upper_bound_candidates_per_hour": round(total_candidates / hours, 3),
        },
        "files": reports,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
