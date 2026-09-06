CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS owner_accounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  display_name text NOT NULL,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'deleted')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS clubs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_account_id uuid NOT NULL REFERENCES owner_accounts(id),
  name text NOT NULL,
  timezone text NOT NULL DEFAULT 'America/Argentina/Buenos_Aires',
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'archived'))
);

CREATE TABLE IF NOT EXISTS fields (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  club_id uuid NOT NULL REFERENCES clubs(id),
  sport_code text NOT NULL,
  name text NOT NULL,
  qr_token_hash text NOT NULL UNIQUE,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'maintenance')),
  UNIQUE (club_id, name)
);

CREATE TABLE IF NOT EXISTS cameras (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  field_id uuid NOT NULL REFERENCES fields(id),
  device_id text NOT NULL UNIQUE,
  label text NOT NULL,
  status text NOT NULL DEFAULT 'offline' CHECK (status IN ('online', 'offline', 'maintenance', 'retired')),
  last_seen_at timestamptz
);

CREATE TABLE IF NOT EXISTS players (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_account_id uuid NOT NULL REFERENCES owner_accounts(id),
  display_name text NOT NULL,
  phone_e164 text NOT NULL,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'blocked', 'deleted')),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  club_id uuid NOT NULL REFERENCES clubs(id),
  field_id uuid NOT NULL REFERENCES fields(id),
  camera_id uuid NOT NULL REFERENCES cameras(id),
  sport_code text NOT NULL,
  session_token_hash text NOT NULL UNIQUE,
  started_at timestamptz NOT NULL,
  ended_at timestamptz,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('pending', 'active', 'ending', 'completed', 'partial', 'failed', 'cancelled')),
  responsible_player_id uuid NOT NULL REFERENCES players(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS sessions_one_active_per_field
  ON sessions (field_id) WHERE status IN ('pending', 'active', 'ending');

CREATE TABLE IF NOT EXISTS highlights (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL REFERENCES sessions(id),
  source_event_id uuid NOT NULL UNIQUE,
  occurred_at timestamptz NOT NULL,
  window_start_at timestamptz NOT NULL,
  window_end_at timestamptz NOT NULL,
  status text NOT NULL DEFAULT 'processing' CHECK (status IN ('requested', 'processing', 'available', 'failed', 'expired', 'deleted')),
  storage_key text
);

CREATE INDEX IF NOT EXISTS highlights_session_occurred_idx ON highlights (session_id, occurred_at DESC);
