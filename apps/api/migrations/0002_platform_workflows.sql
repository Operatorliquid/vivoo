CREATE TABLE IF NOT EXISTS owner_memberships (
  owner_account_id uuid NOT NULL REFERENCES owner_accounts(id),
  identity_id text NOT NULL,
  role text NOT NULL DEFAULT 'owner' CHECK (role IN ('owner', 'admin', 'operator', 'viewer')),
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (owner_account_id, identity_id)
);

CREATE TABLE IF NOT EXISTS venues (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  club_id uuid NOT NULL REFERENCES clubs(id),
  name text NOT NULL,
  address text,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
  UNIQUE (club_id, name)
);

ALTER TABLE fields ADD COLUMN IF NOT EXISTS venue_id uuid REFERENCES venues(id);
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS venue_id uuid REFERENCES venues(id);

CREATE TABLE IF NOT EXISTS sport_capabilities (
  sport_code text PRIMARY KEY,
  capability_version text NOT NULL,
  trigger_types text[] NOT NULL DEFAULT ARRAY['manual'],
  configuration jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'experimental', 'retired'))
);

CREATE TABLE IF NOT EXISTS consent_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  player_id uuid NOT NULL REFERENCES players(id),
  session_id uuid NOT NULL REFERENCES sessions(id),
  recording_consent boolean NOT NULL,
  messaging_consent boolean NOT NULL,
  policy_version text NOT NULL,
  source text NOT NULL DEFAULT 'qr_flow' CHECK (source IN ('qr_flow', 'owner_entry', 'admin_update')),
  captured_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS session_players (
  session_id uuid NOT NULL REFERENCES sessions(id),
  player_id uuid NOT NULL REFERENCES players(id),
  role text NOT NULL DEFAULT 'participant' CHECK (role IN ('responsible', 'participant')),
  joined_at timestamptz NOT NULL DEFAULT now(),
  left_at timestamptz,
  PRIMARY KEY (session_id, player_id)
);

CREATE TABLE IF NOT EXISTS recordings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL REFERENCES sessions(id),
  camera_id uuid NOT NULL REFERENCES cameras(id),
  storage_key text,
  start_time timestamptz NOT NULL,
  end_time timestamptz,
  duration_seconds integer NOT NULL DEFAULT 0 CHECK (duration_seconds >= 0),
  status text NOT NULL DEFAULT 'capturing' CHECK (status IN ('capturing', 'uploading', 'available', 'partial', 'failed', 'deleted')),
  checksum text
);

CREATE TABLE IF NOT EXISTS capture_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL REFERENCES sessions(id),
  camera_id uuid NOT NULL REFERENCES cameras(id),
  event_type text NOT NULL CHECK (event_type IN ('gesture', 'manual', 'physical_button', 'automatic_sport_event')),
  occurred_at timestamptz NOT NULL,
  confidence numeric CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
  source_id text NOT NULL UNIQUE,
  status text NOT NULL DEFAULT 'accepted' CHECK (status IN ('accepted', 'rejected', 'processed', 'failed'))
);

ALTER TABLE highlights ADD COLUMN IF NOT EXISTS recording_id uuid REFERENCES recordings(id);
ALTER TABLE highlights ADD COLUMN IF NOT EXISTS capture_event_id uuid REFERENCES capture_events(id);
ALTER TABLE highlights ADD COLUMN IF NOT EXISTS requested_by_player_id uuid REFERENCES players(id);
ALTER TABLE highlights ADD COLUMN IF NOT EXISTS duration_seconds integer CHECK (duration_seconds IS NULL OR duration_seconds >= 0);
ALTER TABLE highlights ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();

CREATE TABLE IF NOT EXISTS processing_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_type text NOT NULL CHECK (job_type IN ('assemble_highlight', 'transcode', 'thumbnail', 'send_delivery', 'expire_media')),
  resource_id uuid NOT NULL,
  idempotency_key text NOT NULL UNIQUE,
  status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'leased', 'succeeded', 'retryable', 'dead_letter', 'cancelled')),
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  available_at timestamptz NOT NULL DEFAULT now(),
  lease_expires_at timestamptz,
  last_error jsonb
);

CREATE TABLE IF NOT EXISTS deliveries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  highlight_id uuid NOT NULL REFERENCES highlights(id),
  player_id uuid NOT NULL REFERENCES players(id),
  channel text NOT NULL DEFAULT 'whatsapp' CHECK (channel IN ('whatsapp')),
  destination text NOT NULL,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'queued', 'sent', 'delivered', 'failed', 'revoked', 'expired')),
  provider_message_id text,
  last_error jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_account_id uuid REFERENCES owner_accounts(id),
  actor_identity_id text,
  action text NOT NULL,
  resource_type text NOT NULL,
  resource_id uuid,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS highlights_session_event_idx ON highlights (session_id, capture_event_id) WHERE capture_event_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS session_players_unique_idx ON session_players (session_id, player_id);
CREATE INDEX IF NOT EXISTS sessions_club_started_idx ON sessions (club_id, started_at DESC);
CREATE INDEX IF NOT EXISTS processing_jobs_ready_idx ON processing_jobs (status, available_at);
CREATE INDEX IF NOT EXISTS deliveries_highlight_status_idx ON deliveries (highlight_id, status);
