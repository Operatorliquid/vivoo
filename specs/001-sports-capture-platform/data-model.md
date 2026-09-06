# Data Model: Sports Capture Platform

## Modeling Rules

- Every protected record carries or derives an `owner_account_id` boundary.
- Historical media keeps immutable references to the club, venue, field, camera,
  sport, and session that produced it.
- Phone numbers are stored in normalized form and are never exposed to another
  player through player-facing pages.
- Processing and delivery are stateful records, not inferred from file existence.
- Provider-specific identifiers and payloads stay in integration metadata fields or
  provider adapter storage, not in sport or media domain rules.

## Entities

### OwnerAccount

Represents a platform customer or operator.

| Field | Type | Rules |
|---|---|---|
| id | UUID | Primary identifier |
| display_name | string | Required |
| status | enum | `active`, `suspended`, `deleted` |
| created_at | timestamp | Immutable |
| updated_at | timestamp | Updated on change |

### OwnerMembership

Connects an authenticated identity to an owner account.

| Field | Type | Rules |
|---|---|---|
| owner_account_id | UUID | Required |
| identity_id | UUID | Required |
| role | enum | `owner`, `admin`, `operator`, `viewer` |
| status | enum | `active`, `revoked` |

The pair `(owner_account_id, identity_id)` is unique. Permissions are checked
through membership before any protected resource is returned or changed.

### Club

Represents a sports business managed by an owner.

| Field | Type | Rules |
|---|---|---|
| id | UUID | Primary identifier |
| owner_account_id | UUID | Required; immutable after creation |
| name | string | Required |
| timezone | string | Required; used for session display and retention jobs |
| branding | JSON | Optional logo, colors, and share watermark settings |
| status | enum | `active`, `suspended`, `archived` |

### Venue

Represents a physical location inside a club.

| Field | Type | Rules |
|---|---|---|
| id | UUID | Primary identifier |
| club_id | UUID | Required |
| name | string | Required |
| address | string | Optional |
| status | enum | `active`, `inactive` |

### Field

Represents a sports playing area such as a pádel court or football field.

| Field | Type | Rules |
|---|---|---|
| id | UUID | Primary identifier |
| venue_id | UUID | Required |
| sport_code | string | Required; e.g. `padel` |
| name | string | Required; unique within venue |
| qr_token_hash | string | Required; store a hash, not the raw token |
| status | enum | `active`, `inactive`, `maintenance` |

Only one active QR context may resolve to a field. A QR must never encode owner
permissions or raw personal data.

### Camera

Represents a capture source assigned to a field.

| Field | Type | Rules |
|---|---|---|
| id | UUID | Primary identifier |
| field_id | UUID | Required |
| device_id | string | Required; unique |
| label | string | Required |
| status | enum | `online`, `offline`, `maintenance`, `retired` |
| last_seen_at | timestamp | Updated by agent heartbeat |
| capture_profile | JSON | Resolution, frame rate, segment duration, and capability flags |

Historical recordings retain the camera ID even after the field is reassigned.

### SportCapability

Represents sport-specific event and inference configuration.

| Field | Type | Rules |
|---|---|---|
| sport_code | string | Primary identifier |
| capability_version | string | Required and immutable for an event |
| trigger_types | array | Supported event names, including `gesture` and `manual` |
| configuration | JSON | Thresholds and model-independent settings |
| status | enum | `active`, `experimental`, `retired` |

The core platform consumes normalized events and does not depend on model class
names.

### Player

Represents a player contact used for session association and delivery.

| Field | Type | Rules |
|---|---|---|
| id | UUID | Primary identifier |
| owner_account_id | UUID | Scope of the club relationship |
| display_name | string | Required |
| phone_e164 | string | Required for WhatsApp delivery; encrypted at rest |
| status | enum | `active`, `blocked`, `deleted` |
| created_at | timestamp | Required |

Player identities may be reused within the same owner account only after an
explicit matching or confirmation rule. A player-facing session must not expose
the full number.

### ConsentRecord

Records the player's consent for recording and messaging.

| Field | Type | Rules |
|---|---|---|
| id | UUID | Primary identifier |
| player_id | UUID | Required |
| session_id | UUID | Required |
| recording_consent | boolean | Required |
| messaging_consent | boolean | Required for automated WhatsApp delivery |
| policy_version | string | Required |
| captured_at | timestamp | Required |
| source | enum | `qr_flow`, `owner_entry`, `admin_update` |

Consent is append-only for audit purposes; a later withdrawal is represented as
a new event or status change, never by deleting the original record.

### Session

Represents one player activity period on a field.

| Field | Type | Rules |
|---|---|---|
| id | UUID | Primary identifier |
| club_id | UUID | Required |
| venue_id | UUID | Required |
| field_id | UUID | Required |
| camera_id | UUID | Required at confirmation |
| sport_code | string | Required |
| started_at | timestamp | Required |
| ended_at | timestamp | Nullable until ended |
| status | enum | `pending`, `active`, `ending`, `completed`, `partial`, `failed`, `cancelled` |
| responsible_player_id | UUID | Required for first release |
| join_token_hash | string | Required for additional players |

An active session is unique per field and configured time overlap unless an
authorized override is recorded.

### SessionPlayer

Join entity between a session and a player.

| Field | Type | Rules |
|---|---|---|
| session_id | UUID | Required |
| player_id | UUID | Required |
| role | enum | `responsible`, `participant` |
| joined_at | timestamp | Required |
| left_at | timestamp | Nullable |

The pair `(session_id, player_id)` is unique.

### Recording

Represents source media for a session.

| Field | Type | Rules |
|---|---|---|
| id | UUID | Primary identifier |
| session_id | UUID | Required |
| camera_id | UUID | Required |
| storage_key | string | Nullable until uploaded |
| start_time | timestamp | Required |
| end_time | timestamp | Nullable while active |
| duration_seconds | integer | Non-negative |
| status | enum | `capturing`, `uploading`, `available`, `partial`, `failed`, `deleted` |
| checksum | string | Required after upload when available |

### CaptureEvent

Represents a normalized event emitted by a capture agent or future sport service.

| Field | Type | Rules |
|---|---|---|
| id | UUID | Primary identifier |
| session_id | UUID | Required |
| camera_id | UUID | Required |
| event_type | enum | `gesture`, `manual`, `physical_button`, `automatic_sport_event` |
| occurred_at | timestamp | Required |
| confidence | decimal | Nullable for manual events; range 0–1 otherwise |
| source_id | string | Agent event ID; unique for idempotency |
| status | enum | `accepted`, `rejected`, `processed`, `failed` |

### Highlight

Represents a clip derived from a recording.

| Field | Type | Rules |
|---|---|---|
| id | UUID | Primary identifier |
| session_id | UUID | Required |
| recording_id | UUID | Required |
| capture_event_id | UUID | Required |
| requested_by_player_id | UUID | Nullable |
| start_time | timestamp | Required |
| end_time | timestamp | Required; normally event time |
| duration_seconds | integer | Normally 30 or less at session start |
| storage_key | string | Nullable until available |
| status | enum | `requested`, `processing`, `available`, `failed`, `expired`, `deleted` |
| created_at | timestamp | Required |

The tuple `(session_id, capture_event_id)` is unique. A confirmed event must not
be silently replaced by a later event.

### ProcessingJob

Represents retryable media or delivery work.

| Field | Type | Rules |
|---|---|---|
| id | UUID | Primary identifier |
| job_type | enum | `assemble_highlight`, `transcode`, `thumbnail`, `send_delivery`, `expire_media` |
| resource_id | UUID | Highlight, recording, or delivery ID |
| idempotency_key | string | Required and unique per logical action |
| status | enum | `queued`, `leased`, `succeeded`, `retryable`, `dead_letter`, `cancelled` |
| attempts | integer | Starts at 0 |
| available_at | timestamp | Required |
| lease_expires_at | timestamp | Nullable |
| last_error | JSON | Nullable; safe diagnostic data only |

Workers lease jobs, renew leases while active, and make retry decisions based on
classified errors.

### Delivery

Represents a player-facing media delivery.

| Field | Type | Rules |
|---|---|---|
| id | UUID | Primary identifier |
| highlight_id | UUID | Required |
| player_id | UUID | Required |
| channel | enum | `whatsapp`, `web_link` |
| destination_hash | string | Required; do not expose the raw number |
| access_token_hash | string | Required for link delivery |
| status | enum | `pending`, `sent`, `delivered`, `read`, `failed`, `revoked`, `expired` |
| provider_message_id | string | Nullable |
| expires_at | timestamp | Required for access link |
| last_error | JSON | Nullable |

### AuditEvent

Append-only record of security, consent, access, deletion, and operational events.

| Field | Type | Rules |
|---|---|---|
| id | UUID | Primary identifier |
| owner_account_id | UUID | Required where applicable |
| actor_type | enum | `owner`, `player`, `agent`, `worker`, `system` |
| actor_id | UUID/string | Nullable for system events |
| action | string | Required |
| resource_type | string | Required |
| resource_id | UUID/string | Required |
| metadata | JSON | Redacted and bounded |
| occurred_at | timestamp | Required |

## Relationships

```text
OwnerAccount
└── Club
    └── Venue
        └── Field ── Camera
             └── Session ── SessionPlayer ── Player
                 ├── ConsentRecord
                 ├── Recording
                 │   └── Highlight ── Delivery
                 ├── CaptureEvent
                 └── ProcessingJob
```

## State Transitions

### Session

```text
pending → active → ending → completed
                       └──→ partial
pending/active → failed
pending/active → cancelled
```

`partial` means a session ended with incomplete source media but still has usable
content. A failed session must include a visible operational reason.

### Recording

```text
capturing → uploading → available
    │            └────→ partial
    └─────────────────→ failed
available/partial → deleted
```

### Highlight

```text
requested → processing → available
                 └────→ failed → processing
available → expired → deleted
available → deleted
```

### Delivery

```text
pending → sent → delivered → read
   │        └──→ failed → pending
   └────────────→ failed
sent/delivered/read → revoked → expired
```

Provider status callbacks may move a delivery forward or to `failed`; they must
not move a terminal revoked/expired delivery back to an accessible state.
