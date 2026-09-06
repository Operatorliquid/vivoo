<!--
Sync Impact Report
==================
Version change: 1.0.0 → 1.1.0
Modified principles: template placeholders → five product principles; added VI. Premium Product Experience
Added sections: Product Constraints; Development Workflow & Quality Gates; Premium Product Experience principle
Removed sections: none
Follow-up TODOs: none
-->

# CourtVision Constitution

## Core Principles

### I. Player-First, No-Friction Capture

The primary player journey MUST be possible from the court with a QR code and a
mobile browser or WhatsApp, without requiring a native app or a long registration
flow. A player MUST be able to identify a session, trigger or receive a highlight,
and access the result with clear feedback at every step. The club's operational
workflow MUST require minimal staff intervention.

### II. Tenant Isolation, Consent, and Private Media

Every club and venue MUST have an explicit ownership boundary. Owners MUST only
access the clubs, cameras, sessions, players, and media they are authorized to
manage. Recording and messaging flows MUST communicate what is being captured and
where it will be delivered, obtain the required consent, and provide a privacy
control for shared media. Player-facing links MUST be private by default and MUST
support expiration or revocation.

### III. Sport-Agnostic Core with Sport-Specific Intelligence

The platform MUST model common concepts such as organizations, venues, fields,
cameras, sessions, recordings, highlights, players, and deliveries independently
of a single sport. Sport-specific rules, visual detections, event types, and
analytics MUST be isolated as replaceable capabilities. Pádel is the first
delivery scope; adding football or another sport MUST NOT require rewriting the
platform's identity, permissions, media, or delivery foundations.

### IV. Media Reliability and Session Traceability

Every recording and highlight MUST be traceable to a venue, field, camera, session,
time window, and initiating player when known. The system MUST preserve the source
recording relationship for every generated clip, prevent duplicate deliveries
when processing is retried, and expose clear states for recording, processing,
delivery, failure, and expiration. A temporary failure MUST NOT silently discard a
confirmed highlight; the owner MUST be able to identify and retry failed work.

### V. Verifiable Vertical Slices and Operational Simplicity

Each feature MUST be described by user value, acceptance scenarios, and measurable
success criteria before implementation. Work MUST be delivered in independently
testable vertical slices, starting with the smallest useful pádel experience.
Critical flows MUST be validated with representative video, camera, QR, and
messaging scenarios. Operational complexity, dependencies, and paid services MUST
be justified by a user or business outcome; speculative features remain out of
scope until the core capture-and-delivery loop is reliable.

### VI. Premium Product Experience and Design-System Discipline

Every player-facing and owner-facing surface MUST belong to one coherent visual
system and MUST feel intentionally designed for racket-sport media. The product
MUST define reusable tokens for color, typography, spacing, elevation, borders,
motion, and responsive behavior before building individual screens. Buttons,
forms, tables, dialogs, notifications, empty states, loading states, errors,
navigation, and media players MUST use shared components with documented states;
one-off visual exceptions require a documented product reason. Motion MUST clarify
state or create a sense of sport and energy without blocking access, and every
animated interaction MUST have a reduced-motion behavior. Visual polish is a
release criterion alongside functional correctness because the experience is part
of the club's value proposition.

## Product Constraints

- The first release MUST support a club owner account, at least one venue, one or
  more fields with cameras, QR-based session association, player contact capture,
  continuous recording, 30-second pre-event highlights, and private WhatsApp or
  web delivery.
- The owner experience MUST include a searchable media library scoped to the
  owner's clubs, with filters for sport, venue, field, date, session, player, and
  processing status when those data exist.
- The player experience MUST not expose another player's private contact details
  or unrelated club media.
- Automatic gesture detection MAY be introduced alongside a manual fallback so
  that capture remains usable when visual conditions, distance, occlusion, or
  model confidence prevent reliable detection.
- Retention, storage cost, WhatsApp messaging limits, consent records, and media
  deletion MUST be treated as product requirements rather than deferred solely to
  infrastructure work.

## Development Workflow & Quality Gates

- Product intent MUST be recorded in `specs/` before implementation begins.
- A feature MUST pass specification quality review and have an implementation plan
  and actionable tasks before it enters development, unless an explicitly
  documented emergency fix is required.
- Changes affecting permissions, media privacy, recording association, highlight
  generation, or outbound messaging MUST include automated tests and an end-to-end
  acceptance scenario.
- Every implementation MUST define its failure behavior, observability needs, and
  recovery path for camera disconnects, upload failures, processing failures, and
  messaging failures.
- A change is complete only when its acceptance scenarios pass and the owner and
  player journeys remain understandable on a real mobile device.

## Governance

This constitution is the governing product and engineering standard for
CourtVision. Feature specifications, plans, tasks, and implementation decisions
MUST comply with it. When a proposed change conflicts with a principle, the
conflict MUST be documented in the relevant specification and resolved before
implementation.

Amendments require a written rationale, an updated Sync Impact Report, a semantic
version change, and a review of affected specifications and plans. A MAJOR version
is required for removing or redefining a principle; a MINOR version is required
for adding a principle or materially expanding governance; a PATCH version is for
clarifications that do not change the governing intent. Compliance MUST be checked
as part of specification review and before declaring a feature complete.

**Version**: 1.1.0 | **Ratified**: 2026-08-07 | **Last Amended**: 2026-08-07
