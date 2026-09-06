# Research: Sports Capture Platform

**Date**: 2026-08-07

## Decision 1: Keep the rolling buffer at the edge

**Decision**: The capture agent will receive the fixed camera stream, maintain a
rolling window of short local video segments, and create an event record when a
gesture or fallback trigger occurs. The agent will upload the selected clip and
session metadata to the platform. Full-session upload is optional and happens
after or during the session according to the configured retention policy.

**Rationale**:

- The 30 seconds preceding the trigger must remain available even if the club's
  internet connection is briefly interrupted.
- Camera streams should not be exposed directly to player browsers or the public
  internet.
- Short segments make recovery, cleanup, and reassembly more predictable than a
  single continuously growing file.
- FFmpeg's segment muxer supports fixed-duration media segments and segment lists,
  which fits a rolling-buffer implementation. See the [FFmpeg formats
  documentation](https://ffmpeg.org/ffmpeg-formats.html#segment_002c-stream_005fsegment_002c-ssegment).

**Alternatives considered**:

- Browser-only recording: rejected because it requires a device inside the court,
  is fragile for fixed cameras, and does not provide a club-managed capture source.
- Upload the complete live stream to the cloud: rejected for the initial pilot due
  to bandwidth cost, latency, and unnecessary exposure of an active camera feed.
- A physical-only DVR workflow: rejected because it makes gesture detection and
  later sport-specific inference harder to evolve.

## Decision 2: Use AWS-native private media storage with application-controlled access

**Decision**: Store recordings and highlights in private object-storage buckets;
store ownership, metadata, and processing state in PostgreSQL. Player and owner
pages request short-lived access URLs only after the application verifies their
scope. For the AWS deployment, use Amazon S3 as the media origin and Amazon
CloudFront signed URLs for playback/download. Use Amazon RDS for PostgreSQL for
application metadata.

**Rationale**:

- Video is large, immutable media and should not be stored inside relational rows.
- The media path can include tenant and session identifiers without making the
  objects publicly enumerable.
- Amazon S3 presigned URLs support time-limited uploads and downloads without
  giving the edge agent or player permanent AWS credentials. See the [Amazon S3
  presigned URL documentation](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html).
- CloudFront signed URLs let the application authorize access before returning a
  time-limited URL for private media delivery. See [CloudFront signed
  URLs](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-signed-urls.html).
- RDS keeps the tenant and workflow metadata inside the AWS account and can use
  Multi-AZ failover when the product's availability requirement justifies it. See
  [RDS Multi-AZ deployments](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZ.html).

**Alternatives considered**:

- Public object URLs: rejected because player videos are private by default.
- Store video blobs in PostgreSQL: rejected because it increases database size
  and couples media delivery to relational storage.
- A Supabase-first deployment: rejected for this project because the target
  environment is AWS and the owner wants the database, media, identity, network,
  audit, and deployment controls inside one cloud account. Supabase remains a
  valid rapid-prototyping option, but it is not the chosen production foundation.

## Decision 3: Model processing as durable, retryable jobs

**Decision**: Clipping, transcoding, thumbnail generation, and message delivery
will be represented as jobs with explicit state, attempt count, lease time,
idempotency key, error details, and retry timestamp. AWS deployment will use Amazon
SQS queues with visibility timeouts and dead-letter queues; local development may
use a database-backed adapter without changing the job contract.

**Rationale**:

- A highlight must not disappear when a worker or provider is temporarily down.
- Media processing and outbound messaging have different failure and retry rules.
- The owner dashboard needs to show pending, failed, delivered, and expired states.
- Idempotency prevents duplicate clips or WhatsApp messages when a retry follows an
  uncertain network response.

**Alternatives considered**:

- Perform clipping inside the web request: rejected because video work can exceed
  request timeouts and block player/owner interactions.
- Fire-and-forget background calls: rejected because failures would be invisible
  and unrecoverable.
- A database-only queue in production: rejected because the AWS deployment already
  benefits from a managed queue with explicit retry and dead-letter semantics. See
  [SQS visibility timeout and DLQ guidance](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html).

## Decision 4: Keep visual inference behind a sport capability interface

**Decision**: The first pádel implementation will expose a gesture/event detector
  through a capability interface. The core platform consumes normalized events such
  as `highlight_requested` with confidence, timestamp, camera, and session; it does
  not know whether the event came from a hand gesture, button, score event, or
  future football detector.

**Rationale**:

- YOLO supports real-time detection, pose, and tracking capabilities, but model
  choice and training will change as camera angle, distance, and sport change. See
  the [Ultralytics documentation](https://docs.ultralytics.com/) and [tracking
  mode reference](https://docs.ultralytics.com/modes/track/).
- Normalized events let the recording and delivery pipeline remain stable while
  inference evolves.
- A manual or physical fallback keeps the product usable when confidence is low.

**Alternatives considered**:

- Hard-code YOLO output classes in the database and web app: rejected because it
  couples the platform to one model and one sport.
- Start with automatic detection of every great play: rejected because it is a
  larger labeling and validation problem than the MVP's explicit trigger.
- Gesture-only capture: rejected because distance, lighting, occlusion, and
  player behavior can make visual triggers unreliable.

## Decision 5: Use a provider adapter for WhatsApp delivery

**Decision**: The domain exposes a `MessageDeliveryPort`; the first production
  adapter targets the WhatsApp Business Platform/Cloud API, while tests use a fake
  provider and development can use a sandbox. Delivery records store consent,
  template/message identifiers, provider status, and errors without exposing
  provider payloads to the rest of the domain.

**Rationale**:

- The product requires automated, auditable delivery rather than a manual share
  button.
- Business-initiated WhatsApp messages use message templates and have provider
  status behavior that must be handled explicitly. See Meta's [WhatsApp Cloud API
  reference](https://www.postman.com/meta/whatsapp-business-platform/documentation/wlk6lh4/whatsapp-cloud-api)
  and [template API examples](https://www.postman.com/meta/whatsapp-business-platform/folder/lczy75a/templates).
- A provider port allows the MVP to be tested without production credentials and
  protects the core model from vendor-specific changes.

**Alternatives considered**:

- Send a video attachment directly from a personal WhatsApp account: rejected
  because it is not a reliable, auditable, multi-tenant business integration.
- Use only email or SMS: rejected because WhatsApp is part of the product's
  promised player experience, though email/web remains a useful fallback later.
- Couple every domain event directly to Meta's payload shape: rejected because it
  makes testing and provider replacement unnecessarily expensive.

## Decision 6: Use a decoupled React/Vite frontend and FastAPI API

**Decision**: The owner dashboard and public QR/player pages will be a React and
Vite single-page frontend. A FastAPI service will expose the API and explicit
domain modules for authorization, session orchestration, media metadata, and
delivery orchestration. The camera agent and media worker remain separate
deployables because they have different network and compute requirements.

**Rationale**:

- Vite provides a lean static build and development workflow for a browser app;
  the official guide includes React TypeScript templates and static production
  output. See the [Vite getting started guide](https://vite.dev/guide/).
- The API and worker use Python so video, camera, and inference code share a
  language and test tooling.
- Explicit module boundaries preserve a path to split API services only when
  traffic or team ownership requires it.
- The edge and media components already have independent operational constraints;
  splitting the web application further would add deployment overhead without
  immediate user value.

**Alternatives considered**:

- Next.js full-stack frontend: rejected because the product does not require
  server-side rendering and the owner explicitly prefers a decoupled frontend.
- Full microservice architecture from day one: rejected as premature complexity
  for a four-field pilot.
- One process for web, camera, and media: rejected because the camera must run in
  the club network and media work can consume CPU independently.

## Decision 7: Use AWS managed identity and container deployment

**Decision**: Use Amazon Cognito User Pools for owner/admin authentication, with
the FastAPI API validating JWTs and applying the application's club membership
authorization. Use containers for the API and workers, initially deployable on a
secured EC2 host with Docker Compose for the pilot and compatible with Amazon ECS
or Fargate when independent scaling is needed.

**Rationale**:

- Cognito User Pools provide a managed user directory and issue JWTs to web
  applications and APIs. See [Cognito User Pools](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools.html).
- ECS/Fargate is a later operational option for running containers without
  managing cluster servers. See [AWS Fargate for ECS](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html).
- Keeping the application in containers makes the first AWS server deployment
  straightforward without locking the design to a VM forever.

**Alternatives considered**:

- Build authentication in the application: rejected because owner accounts,
  password recovery, MFA, and token issuance are security-sensitive foundations.
- Deploy everything directly on one public EC2 host: rejected because the database
  and media buckets should remain private, and public traffic should terminate at
  a controlled edge/load-balancing layer.
