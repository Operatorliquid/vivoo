#!/bin/sh
set -eu

if [ "$#" -ne 2 ] || [ "$2" != "RESTORE_VIVOO_BACKUP" ]; then
  echo "Uso: vivoo-restore /backups/AAAAMMDDTHHMMSSZ RESTORE_VIVOO_BACKUP" >&2
  echo "Detené api y media-worker antes de restaurar." >&2
  exit 64
fi

backup_dir=$1
[ -f "$backup_dir/courtvision.dump" ] && [ -f "$backup_dir/evolution.dump" ] && [ -f "$backup_dir/SHA256SUMS" ]
(cd "$backup_dir" && sha256sum -c SHA256SUMS)

PGPASSWORD="$COURTVISION_POSTGRES_PASSWORD" pg_restore --clean --if-exists --exit-on-error \
  --no-owner --no-privileges -h "${COURTVISION_POSTGRES_HOST:-db}" \
  -U "${COURTVISION_POSTGRES_USER:-courtvision}" -d "${COURTVISION_POSTGRES_DB:-courtvision}" \
  "$backup_dir/courtvision.dump"
PGPASSWORD="$EVOLUTION_POSTGRES_PASSWORD" pg_restore --clean --if-exists --exit-on-error \
  --no-owner --no-privileges -h "${EVOLUTION_POSTGRES_HOST:-evolution-db}" \
  -U "${EVOLUTION_POSTGRES_USER:-evolution}" -d "${EVOLUTION_POSTGRES_DB:-evolution}" \
  "$backup_dir/evolution.dump"

echo "Restauración completada. Reiniciá api, media-worker y evolution-api."
