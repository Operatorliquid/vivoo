# Quickstart Validation: Sports Capture Platform

This guide validates the first vertical slice without requiring a live club
installation. It uses a deterministic video fixture, a simulated capture agent,
and a WhatsApp provider fake. A later hardware run replaces only the simulated
agent and provider.

## Prerequisites

- Node.js 22 LTS and package manager configured for the repository.
- Python 3.11 and FFmpeg installed for the capture/media services.
- A local PostgreSQL instance for development, with migrations applied.
- An AWS development account with private S3 buckets, an RDS database, and an SQS
  queue configured through the environment's infrastructure definition; local
  development may use compatible emulators where practical.
- A test owner account and one club with one active pádel field and camera.
- A deterministic fixture video at `packages/test-fixtures/padel-match.mp4`.
- A fake messaging provider enabled for test runs.

## Setup

1. Configure the web application, capture agent, and media worker environment
   variables from their example files. Never commit provider secrets.
2. Apply database migrations and seed one owner, club, venue, field, camera, and
   sport capability.
3. Start the web application and media worker.
4. Start the simulated capture agent against the fixture video and the seeded
   camera.

## End-to-End Scenario

1. Open the generated field QR URL on a mobile viewport.
2. Confirm the page identifies the club, venue, field, and pádel sport.
3. Register a player with a test E.164 phone number and accept recording and
   messaging consent.
4. Confirm that exactly one active session exists for the field.
5. Trigger a manual highlight event at a known timestamp in the fixture.
6. Verify that the capture agent submits one event ID and that retries reuse the
   same ID.
7. Verify that the resulting highlight contains the 30 seconds before the event,
   is linked to the source recording and session, and becomes `available`.
8. Verify that the fake WhatsApp provider receives one message with a private
   access URL and the correct club/field context.
9. Open the player URL and verify that the highlight is playable and no unrelated
   club media is visible.
10. Open the owner dashboard and verify that the session, player, highlight,
    delivery status, and source recording appear in the correct club scope.
11. Force a provider failure, verify the delivery becomes visibly failed, retry it
    from the owner view, and confirm that the final successful retry does not
    create a duplicate highlight.
12. Expire or revoke the player access token and verify the media page returns an
    unavailable result.

## Acceptance Commands

The exact package scripts will be created during task generation, but the intended
checks are:

```text
unit tests for web/domain modules
pytest for capture-agent and media-worker
OpenAPI contract validation
Playwright QR/player/owner end-to-end suite
FFmpeg fixture duration and clip-boundary verification
```

## Hardware Pilot

After the simulated scenario passes, connect one fixed camera to a Linux mini-PC,
run the capture agent with the same camera/field identity, and repeat the scenario
with a real hand gesture and manual fallback. Do not enable a second field until
health reporting, disk pressure behavior, network recovery, private links, and
WhatsApp delivery have passed on the first field.
