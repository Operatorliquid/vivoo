# Tasks: Sports Capture Platform

**Input**: Design documents from `/specs/001-sports-capture-platform/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/`, and `quickstart.md`

**Strategy**: Build the smallest complete player value loop first. The recommended
MVP includes User Stories 1–3 because session registration alone is not valuable
without a highlight and private delivery. User Stories 4–6 then make the system
operable as a professional multi-club and multi-sport platform.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the monorepo, frontend, API, Python services, tests, and AWS
infrastructure definitions without implementing product behavior.

- [X] T001 Create the monorepo directory structure from `specs/001-sports-capture-platform/plan.md` in `apps/`, `packages/`, `infra/`, and `tests/`.
- [X] T002 Create the pnpm workspace and root scripts in `package.json` for frontend, contract tests, end-to-end tests, linting, and formatting.
- [X] T003 [P] Initialize the React/Vite TypeScript frontend and wire the shared design-system package in `apps/frontend/package.json`, `apps/frontend/vite.config.ts`, and `apps/frontend/src/main.tsx`.
- [X] T004 [P] Initialize the FastAPI service in `apps/api/pyproject.toml`, `apps/api/src/main.py`, and `apps/api/tests/conftest.py`.
- [X] T005 [P] Initialize the capture agent package in `apps/capture-agent/pyproject.toml`, `apps/capture-agent/src/main.py`, and `apps/capture-agent/tests/conftest.py`.
- [X] T006 [P] Initialize the media worker package in `apps/media-worker/pyproject.toml`, `apps/media-worker/src/main.py`, and `apps/media-worker/tests/conftest.py`.
- [X] T007 [P] Create shared domain contracts, sport capabilities, and CourtVision design-system package scaffolding in `packages/domain-contracts/package.json`, `packages/domain-contracts/src/index.ts`, `packages/sport-capabilities/README.md`, and `packages/design-system/package.json`.
- [X] T008 [P] Create Terraform module scaffolding in `infra/terraform/main.tf`, `infra/terraform/variables.tf`, and `infra/terraform/outputs.tf`.
- [X] T009 [P] Add repository-wide environment examples, ignore rules, and developer commands in `.env.example`, `.gitignore`, and `Makefile`.
- [X] T010 [P] Add baseline lint, format, type-check, visual-regression, and test configuration in `pyproject.toml`, `ruff.toml`, `vitest.config.ts`, `playwright.config.ts`, and `packages/design-system/src/tokens.ts`.

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implement the security, data, media, job, and test foundations required
by every user story. No user-story implementation begins until this phase passes.

- [X] T011 Create the initial PostgreSQL migration structure and migration runner in `apps/api/migrations/0001_initial_schema.sql` and `apps/api/src/db/migrations.py`.
- [X] T012 Implement tenant, membership, club, venue, field, camera, sport, player, consent, session, recording, highlight, delivery, job, and audit tables in `apps/api/migrations/0001_initial_schema.sql` and `apps/api/migrations/0002_platform_workflows.sql`.
- [X] T013 Add database constraints and indexes for tenant scope, active sessions, unique QR token hashes, idempotent capture events, and media search in `apps/api/migrations/0002_platform_workflows.sql`.
- [ ] T014 [P] Implement Cognito JWT verification and owner identity mapping in `apps/api/src/auth/cognito_jwt.py` and `apps/api/src/auth/dependencies.py`.
- [ ] T015 [P] Implement direct owner-to-club scope authorization guards in `apps/api/src/authorization/tenant_scope.py` and `apps/api/src/authorization/policies.py`; do not add staff roles or delegated accounts.
- [ ] T016 [P] Implement structured API errors, correlation IDs, redacted logging, and audit event recording in `apps/api/src/observability/errors.py`, `apps/api/src/observability/logging.py`, and `apps/api/src/observability/audit.py`.
- [ ] T017 [P] Implement AWS configuration and secret loading without repository credentials in `apps/api/src/config.py`, `apps/capture-agent/src/config.py`, and `apps/media-worker/src/config.py`.
- [ ] T018 [P] Implement private S3 media storage, presigned upload targets, and CloudFront signed playback URLs in `apps/api/src/services/media_storage.py` and `apps/api/tests/test_media_storage.py`.
- [ ] T019 [P] Implement SQS job publishing, visibility timeout handling, retry classification, and dead-letter configuration in `apps/api/src/services/job_queue.py` and `apps/media-worker/src/jobs/queue.py`.
- [ ] T020 [P] Copy the OpenAPI definitions and shared request/response types into `packages/domain-contracts/src/openapi.yaml` and `packages/domain-contracts/src/types.ts`.
- [ ] T021 Create local development seed data for one owner, club, venue, pádel field, camera, sport capability, and QR token in `apps/api/src/db/seed.py`.
- [ ] T022 [P] Add deterministic video fixture metadata and a short test clip at `packages/test-fixtures/padel-match.mp4` and `packages/test-fixtures/README.md`.
- [ ] T023 [P] Add contract test helpers for OpenAPI validation and tenant-scoped API clients in `tests/contract/conftest.py` and `tests/contract/openapi_validation.py`.
- [ ] T024 Add a foundational smoke test for configuration, database connectivity, private media access, and queue connectivity in `tests/integration/test_foundation.py`.

**Checkpoint**: Foundation ready. The API can authenticate owners, enforce tenant
scope, persist domain data, create private media targets, and enqueue retryable jobs.

## Phase 3: User Story 1 - Iniciar un partido desde la cancha (Priority: P1)

**Goal**: A player scans a field QR, registers name and phone, accepts consent, and
starts or joins exactly one active session without installing an app.

**Independent Test**: With seeded club/field/camera data, open the QR route on a
mobile viewport, create a session, join it with a second player, and verify the
field context and session associations.

### Tests for User Story 1

- [ ] T025 [P] [US1] Add contract tests for field context, start-session, and join-session endpoints in `tests/contract/test_public_session_api.py`.
- [ ] T026 [P] [US1] Add API integration tests for QR resolution, consent validation, idempotent session creation, and duplicate active-session prevention in `apps/api/tests/test_public_session_flow.py`.
- [ ] T027 [P] [US1] Add Playwright mobile-flow tests for QR context, registration validation, consent, confirmation, and joining an existing session in `tests/e2e/test_qr_session.spec.ts`.

### Implementation for User Story 1

- [ ] T028 [P] [US1] Implement field QR token hashing and public field-context lookup in `apps/api/src/domain/qr_tokens.py` and `apps/api/src/routes/public_fields.py`.
- [ ] T029 [P] [US1] Implement Player, ConsentRecord, Session, and SessionPlayer domain schemas in `apps/api/src/domain/schemas/session.py` and `apps/api/src/domain/schemas/player.py`.
- [ ] T030 [US1] Implement idempotent session start/join service with field overlap validation in `apps/api/src/services/session_service.py`.
- [X] T031 [US1] Expose public field context and session start/join endpoints matching `specs/001-sports-capture-platform/contracts/openapi.yaml` in `apps/api/src/routes/public_sessions.py`.
- [X] T032 [US1] Build the Court After Dark mobile QR landing, player registration, consent, error, and session-confirmation views using shared components in `apps/frontend/src/features/qr/` and `apps/frontend/src/features/player/RegistrationPage.tsx`.
- [ ] T033 [US1] Add API client, session-token handling, and mobile error states in `apps/frontend/src/lib/api.ts` and `apps/frontend/src/features/player/sessionClient.ts`.
- [ ] T034 [US1] Add local seed and demo commands that generate a field QR URL and an active test session in `apps/api/src/db/seed.py` and `apps/api/src/cli.py`.

**Checkpoint**: A player can complete QR registration and the API has one
tenant-scoped, consented session ready to receive capture events.

## Phase 4: User Story 2 - Guardar y recibir un highlight (Priority: P1)

**Goal**: A capture event from a manual trigger or simulated gesture preserves the
30 seconds before the event, processes a highlight, and queues delivery.

**Independent Test**: With one active session and the deterministic fixture, submit
one event, retry it with the same source ID, verify exactly one highlight, and verify
the clip boundary and processing state.

### Tests for User Story 2

- [ ] T035 [P] [US2] Add contract tests for capture heartbeat, capture event, and presigned upload endpoints in `tests/contract/test_capture_agent_api.py`.
- [ ] T036 [P] [US2] Add API integration tests for event idempotency, 30-second window calculation, and job creation in `apps/api/tests/test_highlight_event_flow.py`.
- [ ] T037 [P] [US2] Add media-worker tests for FFmpeg clip boundaries, short-session behavior, and retryable failures in `apps/media-worker/tests/test_highlight_processor.py`.
- [ ] T038 [P] [US2] Add simulated edge-agent tests for rolling buffer retention and network retry behavior in `apps/capture-agent/tests/test_rolling_buffer.py`.
- [ ] T039 [P] [US2] Add an end-to-end highlight test with fake capture and fake messaging providers in `tests/e2e/test_highlight_delivery.spec.ts`.

### Implementation for User Story 2

- [X] T040 [P] [US2] Implement time-segmented rolling buffer storage and cleanup in `apps/capture-agent/src/buffer/rolling_buffer.py`.
- [ ] T041 [P] [US2] Implement camera fixture playback and manual-trigger simulator in `apps/capture-agent/src/camera/fixture_camera.py` and `apps/capture-agent/src/triggers/manual_trigger.py`.
- [X] T042 [P] [US2] Implement normalized sport event and inference interfaces with a deterministic gesture stub in `apps/capture-agent/src/inference/events.py`.
- [ ] T042A [US2] Implement and calibrate real CPU-capable arms-up pose inference against the pilot camera in `apps/capture-agent/src/inference/arms_up.py`, `apps/capture-agent/src/inference/yolo_pose.py`, and `apps/capture-agent/src/inference/monitor.py`.
- [ ] T043 [US2] Implement capture-agent heartbeat, idempotent event submission, upload checkpointing, and retry logic in `apps/capture-agent/src/health/heartbeat.py`, `apps/capture-agent/src/uploads/client.py`, and `apps/capture-agent/src/events/client.py`.
- [X] T044 [US2] Implement authenticated capture-agent event ingestion and presigned upload routes in `apps/api/src/routes/agent_events.py` and `apps/api/src/routes/agent_uploads.py`.
- [X] T045 [US2] Implement highlight window calculation, capture-event persistence, and idempotent `assemble_highlight` job creation in `apps/api/src/services/store.py`.
- [ ] T046 [US2] Implement FFmpeg source-segment assembly, clip validation, thumbnail generation, and highlight status transitions in `apps/media-worker/src/clipping/highlight_processor.py` and `apps/media-worker/src/clipping/ffmpeg.py`.
- [ ] T047 [US2] Implement media-worker job lifecycle, S3 upload, checksum verification, and failure recovery in `apps/media-worker/src/jobs/worker.py` and `apps/media-worker/src/jobs/retry_policy.py`.
- [ ] T048 [US2] Implement fake messaging provider and delivery job creation for local validation in `apps/media-worker/src/delivery/fake_provider.py` and `apps/api/src/services/delivery_service.py`.

**Checkpoint**: A real or simulated event creates one playable 30-second highlight
and leaves a visible, retryable delivery job.

## Phase 5: User Story 3 - Consultar el partido y sus momentos (Priority: P1)

**Goal**: A player opens a private page, plays available highlights or the full
recording when authorized, and loses access after expiry or revocation.

**Independent Test**: Use a valid player access token to view only the session's
media, then expire/revoke the token and confirm the same content is inaccessible.

### Tests for User Story 3

- [ ] T049 [P] [US3] Add contract tests for private access-page and media URL authorization in `tests/contract/test_player_media_api.py`.
- [ ] T050 [P] [US3] Add API security tests for token scope, expiry, revocation, and cross-session access denial in `apps/api/tests/test_player_media_access.py`.
- [ ] T051 [P] [US3] Add Playwright tests for highlight playback, full-recording availability, expired links, and revoked links in `tests/e2e/test_player_media_page.spec.ts`.

### Implementation for User Story 3

- [ ] T052 [P] [US3] Implement hashed player access tokens, expiry, revocation, and audit events in `apps/api/src/services/player_access_service.py`.
- [ ] T053 [US3] Implement private player media-page and signed-URL endpoints in `apps/api/src/routes/public_access.py`.
- [ ] T054 [US3] Build the editorial private player media page, highlight list, playback states, and access-expired view using shared media components in `apps/frontend/src/features/player/MediaPage.tsx` and `apps/frontend/src/features/player/HighlightList.tsx`.
- [ ] T055 [US3] Implement CloudFront signed-URL generation and media delivery status refresh in `apps/frontend/src/lib/mediaUrls.ts` and `apps/api/src/services/media_access.py`.
- [ ] T056 [US3] Implement WhatsApp delivery adapter contract, fake provider status callbacks, and idempotent delivery records in `apps/media-worker/src/delivery/whatsapp_port.py`, `apps/media-worker/src/delivery/fake_provider.py`, and `apps/api/src/routes/webhooks.py`.
- [ ] T057 [US3] Implement delivery retry and provider-status handling for sent, delivered, failed, revoked, and expired states in `apps/media-worker/src/delivery/delivery_worker.py` and `apps/api/src/services/delivery_service.py`.
- [ ] T058 [US3] Add player-facing delivery status copy and resend-safe UX in `apps/frontend/src/features/player/DeliveryStatus.tsx`.

**Checkpoint**: The core MVP loop works: QR registration → session → highlight →
private page → fake WhatsApp delivery.

## Phase 6: User Story 4 - Administrar clubes y biblioteca de videos (Priority: P1)

**Goal**: Owners authenticate, see only their clubs, search media, and inspect
session processing and delivery state.

**Independent Test**: Create two owner accounts with separate clubs, populate media,
and verify each owner can find only its own session and retry its own failed delivery.

### Tests for User Story 4

- [ ] T059 [P] [US4] Add contract tests for owner club, media search, session detail, and delivery retry endpoints in `tests/contract/test_owner_media_api.py`.
- [ ] T060 [P] [US4] Add tenant-isolation integration tests for direct ownership and cross-owner/cross-club access in `apps/api/tests/test_owner_authorization.py`.
- [ ] T061 [P] [US4] Add Playwright tests for owner login, media filters, session detail, failure state, and retry action in `tests/e2e/test_owner_dashboard.spec.ts`.

### Implementation for User Story 4

- [ ] T062 [P] [US4] Implement Cognito sign-in callback, owner session handling, and logout in `apps/frontend/src/features/owner/auth/`.
- [ ] T063 [P] [US4] Implement owner club and media-search schemas, filters, pagination, and authorization in `apps/api/src/routes/owner_media.py` and `apps/api/src/services/media_search.py`.
- [ ] T064 [US4] Implement owner session-detail and delivery-retry endpoints in `apps/api/src/routes/owner_sessions.py` and `apps/api/src/routes/owner_deliveries.py`.
- [ ] T065 [US4] Build the premium owner command center, club switcher, media table, filters, session detail, camera-health strip, and retry controls using the design system in `apps/frontend/src/features/owner/`.
- [ ] T066 [US4] Add audit-event views and safe operational diagnostics for owners in `apps/api/src/routes/owner_audit.py` and `apps/frontend/src/features/owner/AuditPanel.tsx`.

**Checkpoint**: A club owner can operate the product without database access and
cannot see another owner's media.

## Phase 7: User Story 5 - Configurar una cancha y preparar una sesión (Priority: P2)

**Goal**: A club administrator manages fields, cameras, QR identifiers, and camera
health from the owner experience.

**Independent Test**: Create a field/camera, generate its QR, connect a simulated
agent heartbeat, disable the camera, and verify the player flow reflects health.

### Tests for User Story 5

- [ ] T067 [P] [US5] Add contract tests for club, venue, field, camera, QR, and heartbeat administration in `tests/contract/test_club_configuration_api.py`.
- [ ] T068 [P] [US5] Add API integration tests for historical camera association, field status, QR rotation, and heartbeat transitions in `apps/api/tests/test_club_configuration.py`.
- [ ] T069 [P] [US5] Add Playwright tests for field/camera setup and QR display in `tests/e2e/test_club_configuration.spec.ts`.

### Implementation for User Story 5

- [ ] T070 [P] [US5] Implement club, venue, field, camera, sport assignment, and QR configuration services in `apps/api/src/services/club_configuration.py`.
- [ ] T071 [US5] Implement owner-only configuration routes in `apps/api/src/routes/owner_configuration.py`.
- [X] T072 [US5] Implement camera heartbeat state updates and offline alerts in `apps/api/src/services/store.py` and `apps/api/src/routes/agent_events.py`.
- [ ] T073 [US5] Build club configuration, camera health, QR generation, and QR rotation views with shared form, dialog, alert, and status components in `apps/frontend/src/features/owner/configuration/`.
- [ ] T074 [US5] Add Terraform resources for private networking, RDS, S3, CloudFront, Cognito, SQS, IAM roles, and CloudWatch alarms in `infra/terraform/`.

**Checkpoint**: A club can add a new field and connect an agent without code or
database edits.

## Phase 8: User Story 6 - Preparar la expansión a otros deportes (Priority: P3)

**Goal**: Sport-specific events and settings remain replaceable while the common
owner, player, session, media, and delivery journeys stay unchanged.

**Independent Test**: Register a second sport capability and create a field/session
for it without altering existing pádel records or owner media flows.

### Tests for User Story 6

- [ ] T075 [P] [US6] Add contract tests for sport capability registration and normalized event schemas in `tests/contract/test_sport_capabilities.py`.
- [ ] T076 [P] [US6] Add integration tests proving a second sport reuses tenant/media/delivery services without mixing sport-specific configuration in `apps/api/tests/test_sport_capability_boundary.py`.

### Implementation for User Story 6

- [ ] T077 [P] [US6] Implement sport capability registry and versioned configuration in `apps/api/src/services/sport_capabilities.py` and `packages/sport-capabilities/src/index.ts`.
- [ ] T078 [US6] Add a non-production football capability stub with normalized event examples in `packages/sport-capabilities/src/football.ts`.
- [ ] T079 [US6] Expose sport capability selection in field configuration without changing common session/media services in `apps/api/src/routes/owner_configuration.py` and `apps/frontend/src/features/owner/configuration/SportSelector.tsx`.

**Checkpoint**: A new sport can be introduced as a capability rather than a rewrite.

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Harden the MVP for an AWS pilot, complete shared visual quality, and
validate the complete quickstart. T087–T090 are a design-system gate: their
implementation must be pulled forward immediately after foundational setup and
before any feature-specific frontend surface is considered complete.

- [ ] T080 [P] Add Dockerfiles and local Docker Compose orchestration for API, frontend preview, capture agent, and media worker in `apps/api/Dockerfile`, `apps/capture-agent/Dockerfile`, `apps/media-worker/Dockerfile`, and `docker-compose.yml`.
- [ ] T081 [P] Add CI workflows for type checks, Python tests, contract tests, frontend build, and Playwright smoke tests in `.github/workflows/ci.yml`.
- [ ] T082 [P] Add security checks for dependency audit, secret scanning, S3 public-access blocking, JWT validation, and signed-URL expiration in `tests/security/` and `.github/workflows/security.yml`.
- [ ] T083 [P] Add responsive mobile and owner-dashboard accessibility checks in `apps/frontend/tests/accessibility.spec.ts`.
- [ ] T084 [P] Add retention, deletion, and expiration workers with audit coverage in `apps/media-worker/src/jobs/retention_worker.py` and `apps/api/tests/test_retention.py`.
- [ ] T085 Run every scenario in `specs/001-sports-capture-platform/quickstart.md` against local fake providers and record results in `specs/001-sports-capture-platform/validation-results.md`.
- [ ] T086 Document AWS deployment, environment variables, camera-agent installation, rollback, backups, and incident recovery in `docs/deployment.md` and `docs/camera-agent.md`.
- [X] T087 [P] Implement CourtVision color, typography, spacing, radius, elevation, border, z-index, and motion tokens in `packages/design-system/src/tokens.ts` and `packages/design-system/src/theme.css`.
- [X] T088 [P] Implement shared buttons, inputs, forms, dialogs, toasts, alerts, badges, skeletons, empty states, and focus primitives in `packages/design-system/src/components/`.
- [ ] T089 [P] Implement shared media, court-line, camera-health, QR-flow, timeline, video, and navigation components in `packages/design-system/src/components/`.
- [ ] T090 [P] Add reduced-motion, keyboard focus, accessible names, and responsive behavior tests for shared components in `packages/design-system/tests/accessibility.spec.ts` and `packages/design-system/tests/responsive.spec.ts`.
- [X] T091 Run a visual quality audit against `specs/001-sports-capture-platform/design-system.md` and record desktop/mobile screenshots and regressions in `specs/001-sports-capture-platform/visual-validation.md`.

## Phase 10: Session-driven recording controls

**Purpose**: Make the active field session the single source of truth for edge
recording, whether it starts from QR registration or the owner console.

- [X] T092 [P] Add API and capture-agent tests for QR auto-start, owner start/stop,
  heartbeat acknowledgement, segmented recording, and full-match finalization in
  `apps/api/tests/test_recording_controls.py` and
  `apps/capture-agent/tests/test_session_recording.py`.
- [X] T093 Implement active-session lifecycle and owner recording controls in
  `apps/api/src/services/store.py`, `apps/api/src/routes/owner.py`, and
  `apps/api/src/routes/agent_events.py`.
- [X] T094 Implement session-driven segmented recording and bounded highlight
  source extraction in `apps/capture-agent/src/camera/recorder.py`,
  `apps/capture-agent/src/runtime/agent.py`, and
  `apps/capture-agent/src/client/api_client.py`.
- [X] T095 Build recording status and start/stop controls with shared components
  in `apps/frontend/src/features/courts/CourtDetailPage.tsx`,
  `apps/frontend/src/lib/api.ts`, and `apps/frontend/src/styles/detail.css`.
- [X] T096 Deploy the API/frontend, restart the local edge agent, and validate QR
  and owner-driven recording against the linked camera.

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; T003–T010 can run in parallel after T001/T002 establish the workspace.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories.
- **Design-system gate (T087–T090)**: Depends on the frontend/package scaffolding
  from Setup and must complete before T032, T054, T065, T073, or any other
  feature-specific frontend component is accepted.
- **User Story 1 (Phase 3)**: Depends on Foundational; first player-facing increment.
- **User Story 2 (Phase 4)**: Depends on US1 because events require an active session; capture-agent fixture work can start in parallel after Foundational.
- **User Story 3 (Phase 5)**: Depends on US2 because the page needs generated highlights; access-token work can start in parallel with late US2 work.
- **User Story 4 (Phase 6)**: Depends on Foundational and the media/session records from US1–US3.
- **User Story 5 (Phase 7)**: Depends on Foundational; configuration API work can proceed in parallel with US3/US4, but the complete operator flow integrates after US4.
- **User Story 6 (Phase 8)**: Depends on the common domain and capability boundary from US1–US5.
- **Polish (Phase 9)**: Depends on the desired MVP stories; AWS Terraform and Docker can begin earlier but are validated here.

### User Story Completion Order

```text
Foundational → US1 → US2 → US3 → MVP checkpoint
                         ↘ US4
Foundational → US5 ────────┘
US1–US5 → US6 → Polish
```

### Parallel Opportunities

- After T001/T002, frontend, API, capture-agent, worker, contracts, and Terraform setup tasks can run in parallel.
- Within Foundational, auth, observability, AWS media storage, queue adapters, and fixture setup can run in parallel after migration structure exists.
- In US2, rolling-buffer, fixture-camera, inference-stub, and contract tests can run in parallel; event ingestion and FFmpeg processing depend on their contracts.
- In US3, access-token, player UI, and contract/security tests can run in parallel once the highlight state contract is stable.
- In US4, owner UI shell, media-search API, authorization tests, and dashboard tests can proceed in parallel after Cognito middleware exists.
- In US5, field configuration, heartbeat, UI, and Terraform modules can proceed in parallel after foundational authorization.

## Parallel Example: MVP

```text
Track A: T025–T034 — public QR/session flow
Track B: T037–T043 — deterministic capture agent and rolling buffer
Track C: T035–T039 — capture/highlight contracts and end-to-end tests
Track D: T049–T058 — private player page and fake delivery
```

Tracks B and C may begin after Foundational; the integrated MVP checkpoint waits
for the active session from US1 and the highlight flow from US2.

## Implementation Strategy

### MVP First

1. Complete Setup and Foundational phases.
2. Complete the design-system gate T087–T090 and validate the shared component states.
3. Complete US1 and validate QR registration on a mobile viewport.
4. Complete US2 using the fixture camera and fake trigger/provider.
5. Complete US3 and validate private media access and expiry.
6. Stop at the MVP checkpoint before adding owner operations or real camera hardware.

### Incremental Delivery

1. Add US4 so a club owner can operate and search the media library.
2. Add US5 so fields and cameras can be configured without database edits.
3. Replace the fixture agent with one real camera and validate the hardware pilot.
4. Add US6's capability boundary before implementing football-specific inference.
5. Complete AWS hardening and the full quickstart validation.

## Notes

- Every task follows the required checklist format with a sequential ID, optional
  `[P]` marker, story label for story phases, and concrete file paths.
- Tests are included because the constitution requires automated and end-to-end
  coverage for media, permissions, recording association, and messaging.
- The first real camera integration is intentionally after the fake end-to-end
  MVP so hardware failures do not obscure product-flow validation.

## Phase 11: Convergence

- [ ] T097 CRITICAL Replace the fixed demo owner with production owner-account registration,
  password hashing, session rotation, recovery, direct ownership mapping, and strict club
  authorization in `apps/api/src/auth/`, `apps/api/src/authorization/`, owner routes,
  migrations, and frontend auth flows. The product has only the owner account type; do
  not add invitations, staff accounts, or selectable roles. Per Constitution II, FR-001,
  FR-001a, and FR-002
  (contradicts).
- [ ] T098 CRITICAL remove shared fallback agent/worker credentials, persist camera-token
  revocation, bind every edge request to its camera and owner, rotate secrets, and add
  negative security tests in `apps/api/src/auth/`, `apps/api/src/routes/agent_events.py`,
  `apps/api/src/routes/worker.py`, and `tests/security/` per Constitution II and FR-002
  (contradicts).
- [ ] T099 CRITICAL implement hashed player access grants with expiration, revocation,
  scoped media authorization, owner controls, and audit events in API, database, and
  player/owner UI per Constitution II, FR-019, and US3/AC3 (missing).
- [ ] T100 CRITICAL make full-recording and highlight uploads durable across network loss,
  session completion, agent restart, and token refresh by storing session-scoped media
  jobs with checksums and bounded retry/cleanup in the capture agent and API per
  Constitution IV, FR-016, and SC-009 (partial).
- [ ] T101 CRITICAL move production media to private S3 with signed playback, lifecycle
  tiers, quotas, checksum verification, and a migration path from local Docker media in
  `apps/api/src/services/media_storage.py`, worker storage, Terraform, and deployment
  configuration per Constitution IV, FR-014, and plan storage decisions (partial).
- [ ] T102 CRITICAL remove cloud persistence of plaintext RTSP/button credentials, keep
  camera secrets at the edge or encrypt them with managed keys, redact all API/log/UI
  representations, and migrate existing rows per Constitution II and FR-020 (contradicts).
- [ ] T103 CRITICAL implement visible retention policies, automatic expiration, deletion
  of recordings/highlights/player data, consent-version history, owner/player deletion
  requests, and immutable audit evidence per Constitution II, FR-020, and FR-023
  (missing).
- [ ] T104 [P] Terminate TLS on a configurable production domain, force HTTPS, add HSTS
  and security headers, remove hard-coded public origins, and provide local-only defaults
  in Nginx/deployment/Terraform per Constitution II and plan AWS deployment decisions
  (missing).
- [ ] T105 implement an idempotent delivery outbox with leases, provider callbacks,
  exponential retry, dead-letter recovery, opt-out handling, and owner retry controls;
  retain Evolution behind a provider-neutral adapter and support an official WhatsApp
  Business adapter per Constitution IV, FR-015, FR-016, and SC-004 (partial).
- [ ] T106 [P] build a self-contained signed CourtVision Desktop installer bundling the
  Python runtime, FFmpeg, MediaMTX, pose model, agent dependencies, service watchdog,
  start-on-boot behavior, logs, and safe updates for the supported pilot OS per
  Constitution V and US5/AC1 (partial).
- [ ] T107 implement a multi-camera edge supervisor with one isolated runtime per field,
  hardware resource limits, restart isolation, per-camera health, and one-PC club setup
  in `apps/desktop/` and `apps/capture-agent/` per SC-008 and US4/AC4 (missing).
- [ ] T108 [P] add structured redacted logs, correlation IDs, metrics, health probes,
  disk/camera/detector/upload/delivery alerts, owner-visible incidents, and production
  dashboards in API, edge, worker, and AWS monitoring per Constitution IV and FR-016
  (partial).
- [ ] T109 [P] add encrypted automated database/media backups, restore verification,
  rollback procedures, disaster-recovery runbooks, and storage-capacity alarms in
  `infra/`, `docs/`, and integration tests per Constitution IV and plan deployment
  decisions (missing).
- [ ] T110 [P] replace hard-coded ESP32 configuration with secure provisioning, device
  identity, acknowledgement feedback, durable press retry, debouncing, heartbeat,
  watchdog, and signed firmware update support per FR-010 and US2/AC2 (partial).
- [ ] T111 [P] add reproducible CI for type checks, isolated Python tests, frontend build,
  contract tests, Playwright journeys, accessibility, dependency/secret/container/IaC
  scanning, and deployment promotion per Constitution V, FR-029, FR-031, and SC-014
  (missing).
- [ ] T112 complete AWS production infrastructure and operating documentation for private
  networking, managed PostgreSQL, S3/CloudFront, secret management, queues, monitoring,
  staging, zero-data-loss migrations, rollback, and cost controls per plan AWS decisions
  and T074/T086 (partial).

## Phase 12: Owner messaging and edge reliability increment

- [X] T113 add owner-scoped Evolution API instances, QR connect/status/disconnect controls,
  internal credentials, persistent Compose services, and per-owner highlight delivery in
  `apps/api/src/services/evolution_service.py`, owner settings UI, worker adapter, and
  `infra/deploy/compose.yml`.
- [X] T114 replace full-file agent PUTs with checksummed, resumable 8 MiB parts and
  idempotent completion in `apps/capture-agent/src/client/api_client.py` and
  `apps/api/src/services/media_storage.py`.
- [X] T115 add real database, storage, disk, and media-worker readiness checks plus a
  separate liveness route in `apps/api/src/services/health_service.py` and worker heartbeat.
- [X] T116 add per-camera local runtime/config/media isolation and camera-addressed local
  control endpoints in `apps/capture-agent/src/runtime/supervisor.py` and vivoo Desktop.
- [X] T117 add background desktop update download and recording-safe automatic install,
  plus the version-feed staging path in `apps/desktop/` and `infra/deploy/`.
