#!/usr/bin/env bash
# Quick mongo dump → /opt/cloudypitch/backups/cp-YYYYMMDD-HHMM.archive
set -euo pipefail
cd "$(dirname "$0")"
. ./.env
ts=$(date -u +%Y%m%d-%H%M)
out_dir="${BACKUP_DIR:-/opt/cloudypitch/backups}"
mkdir -p "$out_dir"
archive="$out_dir/cp-$ts.archive"
docker compose exec -T mongo mongodump \
    --username "$MONGO_USER" --password "$MONGO_PASSWORD" --authenticationDatabase admin \
    --db "$DB_NAME" --archive > "$archive"
printf 'Backup written: %s (%s)\n' "$archive" "$(du -h "$archive" | cut -f1)"
# Prune backups older than 14 days
find "$out_dir" -name 'cp-*.archive' -mtime +14 -delete
