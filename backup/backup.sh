#!/usr/bin/env bash
set -euo pipefail
: "${BACKUP_BUCKET:?}" "${PGPASSWORD:?}"
file="$(mktemp /tmp/tasks-XXXXXX.dump)"
trap 'rm -f "$file"' EXIT
key="tasks/$(date -u +%Y/%m/%d/%Y%m%dT%H%M%SZ)-${HOSTNAME}.dump"
pg_dump --format=custom --no-owner --no-acl --file="$file"
pg_restore --list "$file" >/dev/null
aws s3 cp "$file" "s3://${BACKUP_BUCKET}/${key}" --sse AES256 --only-show-errors
aws s3api head-object --bucket "$BACKUP_BUCKET" --key "$key" --query '{Size:ContentLength,Encryption:ServerSideEncryption}'
printf 'Backup uploaded: s3://%s/%s\n' "$BACKUP_BUCKET" "$key"
