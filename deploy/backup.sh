#!/bin/sh
# Manual maintenance backup: run from the repository root. No automatic schedule.
set -eu
control=${1:-deploy/control.env}
stamp=$(date -u +%Y%m%dT%H%M%SZ)
compose() { docker compose --env-file "$control" -f deploy/compose.yaml "$@"; }
# Backups include database + PDFs; stop writes before taking the snapshot.
# Always attempt to bring the app back after failure or interruption.
trap 'compose up -d app edge' EXIT
trap 'exit 130' INT TERM
compose stop edge app
compose run --rm --no-deps app python manage_release.py backup --output "/backups/$stamp"
compose run --rm --no-deps app python manage_release.py verify --bundle "/backups/$stamp"
printf 'Private backup verified: /backups/%s (copy encrypted off-host before relying on it)\n' "$stamp"
