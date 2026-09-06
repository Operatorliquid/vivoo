# Capture Agent Contract

The capture agent runs inside the club network and is assigned to exactly one
camera at a time. It must not expose the camera stream to public clients.

## Responsibilities

1. Connect to the configured camera and report health at least every 30 seconds.
2. Maintain a rolling buffer with enough media to cover the configured 30-second
   pre-event window plus a safety margin.
3. Run the active sport capability locally when available and normalize detections
   into `CaptureEventRequest` records.
4. Accept manual or physical trigger input as a first-class event source.
5. Upload selected media through short-lived upload targets.
6. Retry transient network failures locally while preserving the original event ID.
7. Report degraded or offline state without inventing recording availability.

## Local State

The agent may persist local segments, active session metadata, upload checkpoints,
event IDs, and checksums. It must not persist owner passwords, player phone numbers,
or long-lived platform access tokens in plaintext.

## Event Semantics

- `source_id` is generated once per detected or manual event and is reused on every
  retry.
- `occurred_at` is the camera-clock event time; the agent must include its clock
  offset or health warning if time synchronization is unavailable.
- `buffer_start_at` and `buffer_end_at` describe the actual available media window.
- If the window is shorter than 30 seconds, the event is still valid but the API
  and player page must show the actual duration.
- Events with confidence below the configured threshold are not submitted as
  automatic gesture events; a manual trigger remains valid without confidence.

## Failure Behavior

| Failure | Agent behavior | Platform behavior |
|---|---|---|
| Camera unavailable | Mark camera degraded/offline and stop claiming capture | Show health state; do not confirm a playable recording |
| Network unavailable | Continue local buffer and queue bounded uploads | Mark media pending; accept later retry with same IDs |
| Storage upload rejected | Keep local media until retry/retention limit | Mark upload failure with safe diagnostic details |
| Worker/API unavailable | Keep event and upload checkpoint locally | Deduplicate when the event eventually arrives |
| Disk pressure | Remove oldest unreferenced segments and raise an alert | Show degraded state to owner |
