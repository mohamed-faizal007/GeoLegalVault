#!/usr/bin/env bash
# Mongo backup helper (Plan Part 31: "Atlas snapshots + weekly mongodump to a
# second free store; restore procedure documented").
#
# Dumps the database named by MONGODB_DB (from the repo-root .env, or already
# exported) via `mongodump` against MONGODB_URI, into a timestamped folder
# under backups/. Run it by hand before a demo, or on a schedule (cron /
# GitHub Actions on a schedule trigger) for the "weekly" cadence the plan
# calls for — this script itself is cadence-agnostic, it just does one dump.
#
# Usage:
#   ./scripts/backup.sh                 # uses .env / already-exported env vars
#   MONGODB_URI=... MONGODB_DB=... ./scripts/backup.sh
#
# Restore:
#   mongorestore --uri "$MONGODB_URI" --nsInclude "$MONGODB_DB.*" backups/<timestamp>/
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

: "${MONGODB_URI:?MONGODB_URI is not set (export it, or put it in the repo-root .env)}"
: "${MONGODB_DB:?MONGODB_DB is not set (export it, or put it in the repo-root .env)}"

if ! command -v mongodump >/dev/null 2>&1; then
  echo "mongodump not found on PATH. Install the MongoDB Database Tools:" >&2
  echo "  https://www.mongodb.com/try/download/database-tools" >&2
  exit 1
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
out_dir="backups/${timestamp}"
mkdir -p "$out_dir"

echo "Dumping database '${MONGODB_DB}' to ${out_dir} ..."
mongodump --uri "$MONGODB_URI" --db "$MONGODB_DB" --out "$out_dir"

echo "Done: ${out_dir}"
echo "Restore with: mongorestore --uri \"\$MONGODB_URI\" \"${out_dir}\""
