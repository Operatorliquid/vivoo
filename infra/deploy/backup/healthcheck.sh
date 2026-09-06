#!/bin/sh
set -eu

marker=${BACKUP_ROOT:-/backups}/last-success.epoch
[ -f "$marker" ] || exit 1
last_success=$(cat "$marker")
now=$(date -u +%s)
maximum_age=$((${BACKUP_INTERVAL_SECONDS:-21600} + 1800))
[ $((now - last_success)) -le "$maximum_age" ]
