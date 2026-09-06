#!/bin/sh
set -eu

BACKUP_ROOT=${BACKUP_ROOT:-/backups}
INTERVAL_SECONDS=${BACKUP_INTERVAL_SECONDS:-21600}
LOCAL_RETENTION_DAYS=${BACKUP_LOCAL_RETENTION_DAYS:-7}

log() {
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

verify_restore() {
  courtvision_dump=$1
  evolution_dump=$2
  verification_root=$(mktemp -d /tmp/vivoo-restore-check.XXXXXX)
  mkdir -p "$verification_root/socket"
  trap 'pg_ctl -D "$verification_root/data" -m immediate stop >/dev/null 2>&1 || true; rm -rf "$verification_root"' EXIT INT TERM

  initdb -D "$verification_root/data" -A trust -U postgres --no-locale >/dev/null
  pg_ctl -D "$verification_root/data" -o "-F -k $verification_root/socket -p 55432 -c listen_addresses=''" -w start >/dev/null
  createdb -h "$verification_root/socket" -p 55432 -U postgres courtvision_verify
  createdb -h "$verification_root/socket" -p 55432 -U postgres evolution_verify
  pg_restore --exit-on-error --no-owner --no-privileges \
    -h "$verification_root/socket" -p 55432 -U postgres -d courtvision_verify "$courtvision_dump"
  pg_restore --exit-on-error --no-owner --no-privileges \
    -h "$verification_root/socket" -p 55432 -U postgres -d evolution_verify "$evolution_dump"
  psql -h "$verification_root/socket" -p 55432 -U postgres -d courtvision_verify -Atqc \
    "SELECT 1 FROM pg_catalog.pg_tables WHERE schemaname='public' LIMIT 1" | grep -qx 1
  psql -h "$verification_root/socket" -p 55432 -U postgres -d evolution_verify -Atqc \
    "SELECT 1 FROM pg_catalog.pg_tables WHERE schemaname='public' LIMIT 1" | grep -qx 1
  pg_ctl -D "$verification_root/data" -m fast -w stop >/dev/null
  rm -rf "$verification_root"
  trap - EXIT INT TERM
}

upload_backup() {
  backup_dir=$1
  backup_bucket=${AWS_S3_BACKUP_BUCKET:-${AWS_S3_MEDIA_BUCKET:-}}
  if [ -z "$backup_bucket" ]; then
    log "AWS_S3_BACKUP_BUCKET no configurado; backup verificado conservado localmente"
    return 0
  fi
  destination="s3://${backup_bucket}/${AWS_S3_BACKUP_PREFIX:-backups/vivoo}/$(basename "$backup_dir")/"
  aws s3 cp "$backup_dir/" "$destination" --recursive --only-show-errors
  log "Backup cifrado por la política del bucket y enviado a $destination"
}

run_backup() {
  timestamp=$(date -u +%Y%m%dT%H%M%SZ)
  temporary_dir="$BACKUP_ROOT/.${timestamp}.partial"
  final_dir="$BACKUP_ROOT/$timestamp"
  rm -rf "$temporary_dir"
  mkdir -p "$temporary_dir"

  log "Iniciando backup consistente de vivoo y Evolution"
  PGPASSWORD="$COURTVISION_POSTGRES_PASSWORD" pg_dump \
    -h "${COURTVISION_POSTGRES_HOST:-db}" -U "${COURTVISION_POSTGRES_USER:-courtvision}" \
    -d "${COURTVISION_POSTGRES_DB:-courtvision}" --format=custom --compress=6 \
    --no-owner --no-privileges --file="$temporary_dir/courtvision.dump"
  PGPASSWORD="$EVOLUTION_POSTGRES_PASSWORD" pg_dump \
    -h "${EVOLUTION_POSTGRES_HOST:-evolution-db}" -U "${EVOLUTION_POSTGRES_USER:-evolution}" \
    -d "${EVOLUTION_POSTGRES_DB:-evolution}" --format=custom --compress=6 \
    --no-owner --no-privileges --file="$temporary_dir/evolution.dump"

  (cd "$temporary_dir" && sha256sum courtvision.dump evolution.dump > SHA256SUMS)
  verify_restore "$temporary_dir/courtvision.dump" "$temporary_dir/evolution.dump"
  printf '%s\n' "$timestamp" > "$temporary_dir/VERIFIED_RESTORE"
  mv "$temporary_dir" "$final_dir"
  upload_backup "$final_dir"
  date -u +%s > "$BACKUP_ROOT/last-success.epoch"
  printf '%s\n' "$final_dir" > "$BACKUP_ROOT/latest"
  PGPASSWORD="$COURTVISION_POSTGRES_PASSWORD" psql \
    -h "${COURTVISION_POSTGRES_HOST:-db}" -U "${COURTVISION_POSTGRES_USER:-courtvision}" \
    -d "${COURTVISION_POSTGRES_DB:-courtvision}" -v ON_ERROR_STOP=1 -c \
    "CREATE TABLE IF NOT EXISTS courtvision_service_heartbeats (service_name text PRIMARY KEY, observed_at timestamptz NOT NULL, metadata jsonb NOT NULL DEFAULT '{}'::jsonb); INSERT INTO courtvision_service_heartbeats(service_name, observed_at, metadata) VALUES ('backup', now(), jsonb_build_object('verified_restore', true, 'backup_id', '$timestamp')) ON CONFLICT(service_name) DO UPDATE SET observed_at=now(), metadata=EXCLUDED.metadata" >/dev/null
  find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime "+$LOCAL_RETENTION_DAYS" -exec rm -rf {} \;
  log "Backup $timestamp creado y restaurado correctamente en una base aislada"
}

mkdir -p "$BACKUP_ROOT"
while true; do
  if ! run_backup; then
    log "ERROR: el backup o su restauración de prueba fallaron; se reintentará en 5 minutos"
    sleep 300
    continue
  fi
  sleep "$INTERVAL_SECONDS"
done
