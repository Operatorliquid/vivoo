# Implementation Plan: Sports Capture Platform

**Branch**: `001-sports-capture-platform` | **Date**: 2026-08-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-sports-capture-platform/spec.md`

## Summary

Build CourtVision as a modular web platform with a multi-tenant owner dashboard,
a frictionless QR/player flow, and a local capture agent for each camera. The
capture agent keeps a rolling local buffer, reports highlight events, and uploads
source media without exposing cameras directly to the public internet. The web
application owns identity, club/field/session/media metadata, private access,
and delivery state. A media worker assembles clips and performs retries. Sport
capabilities are represented as replaceable modules so pádel is the first vertical
slice and football can reuse the platform core later.

## Technical Context

**Language/Version**: TypeScript 5.x with Node.js 22 LTS for the web application;
Python 3.11 for capture and media-processing services

**Primary Dependencies**: React, Vite, React Router, motion for React animation,
boto3/AWS SDK,
Amazon Cognito, Amazon RDS for PostgreSQL, Amazon S3, Amazon CloudFront, Amazon
SQS, FFmpeg, OpenCV, Ultralytics YOLO tracking/pose capability, Playwright,
Vitest, and pytest

**Storage**: Amazon RDS for PostgreSQL for tenant and workflow metadata; private
Amazon S3 buckets for recordings and highlights; Amazon CloudFront signed URLs for
player media access; Amazon SQS with a dead-letter queue for processing and delivery
jobs

**Testing**: Vitest for web/domain units, pytest for Python services, Playwright
for mobile-oriented QR/player and owner-dashboard acceptance flows, OpenAPI
contract tests, and deterministic video fixtures for buffer and clip boundaries

**Target Platform**: React/Vite static frontend served through Amazon S3 and
CloudFront; FastAPI API and Python workers running as containers in AWS; Linux edge
agent running on a club mini-PC or equivalent device connected to fixed cameras

**Project Type**: Multi-tenant SaaS web application plus edge capture and media
processing services

**Performance Goals**: QR onboarding completed in under 2 minutes; p95 public QR
page response under 1 second when the platform is healthy; a confirmed event
visible in the processing queue within 5 seconds; 90% of successfully processed
highlights delivered within 2 minutes of processing completion; owner media search
results visible within 2 seconds for the pilot dataset

**Constraints**: Camera streams stay on the club side of the network; edge capture
must tolerate brief network loss; confirmed highlights must be idempotent and
retryable; RDS and application services must remain in private subnets; S3 buckets
must block public access; private media must require authorization and an expiring
CloudFront URL; secrets must be stored outside the repository; WhatsApp delivery
must be provider-abstracted and consent-aware; the initial pilot supports one
camera per field and four fields per club

**Scale/Scope**: First pilot targets one club with four fields and up to 100
concurrent registered players across sessions. The core data model and tenant
boundaries must support at least 25 clubs and 100 fields without redesign. Initial
sport capability is pádel; football-specific detection, score tracking, billing,
livestreaming, and native mobile apps are deferred.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / Constraint | Plan alignment | Status |
|---|---|---|
| I. Player-first, no-friction capture | QR public route, mobile-first form, no required native app, WhatsApp/link delivery, manual trigger fallback | PASS |
| II. Tenant isolation, consent, and private media | Owner scope on every protected query, Cognito owner identity, private S3 buckets, CloudFront signed URLs, consent records, provider opt-in | PASS |
| III. Sport-agnostic core | Common entities and workflows are sport-neutral; detection and analytics use a `SportCapability` boundary | PASS |
| IV. Media reliability and traceability | Edge buffer, immutable session/camera associations, SQS visibility timeout/DLQ, job states, idempotency keys, retries, failure visibility, source-to-highlight links | PASS |
| V. Verifiable vertical slices and simplicity | Modular monolith plus two focused Python services, deterministic fixtures, contract tests, and a four-field pilot before scale features | PASS |
| VI. Premium product experience and design-system discipline | Shared CourtVision tokens/components, dark-first sports-media direction, motion states, responsive layouts, reduced-motion behavior, and visual regression gates | PASS |
| Product constraint: owner library | Owner dashboard filters by tenant, club, field, sport, date, player, session, and status | PASS |
| Product constraint: WhatsApp | Delivery adapter records consent, template/message status, retries, and provider errors without coupling the domain to one vendor | PASS |

No constitution violations require justification.

## Phase 0: Research Decisions

Research findings are recorded in [research.md](./research.md). The key decisions
are to keep the rolling buffer at the edge, use private object storage with
short-lived access URLs, model processing as retryable jobs, and isolate WhatsApp
and sport-specific inference behind adapters.

## Phase 1: Design

Design artifacts:

- [data-model.md](./data-model.md) defines tenant, media, session, consent, and
  processing entities and state transitions.
- [contracts/](./contracts/) defines the public QR/player, owner, capture-agent,
  and delivery boundaries.
- [design-system.md](./design-system.md) defines the visual direction, tokens,
  shared component states, motion language, responsive composition, and accessibility
  gates for every frontend surface.
- [quickstart.md](./quickstart.md) defines the end-to-end validation path using a
  deterministic video fixture and a messaging sandbox.

## Project Structure

### Documentation (this feature)

```text
specs/001-sports-capture-platform/
├── plan.md
├── research.md
├── data-model.md
├── contracts/
│   ├── openapi.yaml
│   ├── capture-agent.md
│   └── whatsapp-delivery.md
├── design-system.md
├── quickstart.md
├── checklists/
│   └── requirements.md
└── tasks.md                 # created by $speckit-tasks
```

### Source Code (repository root)

```text
apps/
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── features/
│   │   │   ├── owner/
│   │   │   ├── player/
│   │   │   └── qr/
│   │   └── lib/
│   └── tests/
├── api/
│   ├── src/
│   │   ├── auth/
│   │   ├── authorization/
│   │   ├── domain/
│   │   ├── routes/
│   │   ├── services/
│   │   └── main.py
│   └── tests/
├── capture-agent/
│   ├── src/
│   │   ├── camera/
│   │   ├── buffer/
│   │   ├── inference/
│   │   ├── uploads/
│   │   └── health/
│   └── tests/
└── media-worker/
    ├── src/
    │   ├── jobs/
    │   ├── clipping/
    │   ├── transcoding/
    │   └── delivery/
    └── tests/

packages/
├── domain-contracts/
├── design-system/
├── sport-capabilities/
└── test-fixtures/

infra/
└── terraform/
    ├── network/
    ├── identity/
    ├── data/
    ├── media/
    ├── messaging/
    └── compute/

tests/
├── contract/
└── e2e/
```

**Structure Decision**: Use a small monorepo with a React/Vite frontend, a
FastAPI API, and two focused Python services. The frontend is a static single-page
application and does not depend on Next.js or server-side rendering. The edge
capture agent is separated because it must run inside the club network; the media
worker is separated because video processing and delivery retries have different
resource and failure characteristics. Shared domain contracts, the CourtVision
design system, and sport capability interfaces prevent one-off UI and sport logic
from leaking into tenant or media code. AWS
infrastructure is described in Terraform so the secure network, private data
services, queues, IAM roles, and media delivery are reproducible.

## Complexity Tracking

| Addition | Why needed | Simpler alternative rejected because |
|---|---|---|
| Edge capture agent | The 30-second buffer must remain available during short network interruptions and cameras must not be publicly exposed | Recording only in the browser cannot reliably capture fixed cameras or preserve a club-side buffer |
| Separate media worker | Clipping, transcoding, and retryable delivery can be slow or fail independently of the owner/player web experience | Running video work in web requests would create timeouts and make recovery opaque |
| Sport capability boundary | Future football support must reuse accounts, media, permissions, and delivery | Hard-coding pádel event names into core entities would force a redesign for the next sport |
