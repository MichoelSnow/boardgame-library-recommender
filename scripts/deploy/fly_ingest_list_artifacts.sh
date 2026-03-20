#!/usr/bin/env bash

set -euo pipefail

SCRIPT_NAME="$(basename "$0" .sh)"
LOG_DIR="logs/deploy"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/${SCRIPT_NAME}_$(date -u +%Y%m%dT%H%M%SZ).log"
exec > >(tee -a "${LOG_FILE}") 2>&1
echo "Logging to ${LOG_FILE}"

usage() {
  cat <<'EOF'
Usage:
  scripts/deploy/fly_ingest_list_artifacts.sh

Lists ingest artifact files currently present on the Fly ingest volume:
- /app/data/ingest/ranks
- /app/data/ingest/game_data
- /app/data/ingest/ratings
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

if [ $# -gt 0 ]; then
  echo "Error: no positional arguments are supported."
  usage
  exit 1
fi

if ! command -v fly >/dev/null 2>&1; then
  echo "Error: fly CLI is not installed or not on PATH."
  exit 1
fi

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

APP_NAME="${FLY_APP_NAME_INGEST:-bg-lib-ingest}"

echo "App: ${APP_NAME}"
echo "Listing ingest artifacts..."

REMOTE_CMD=$(cat <<'EOF'
list_group() {
  label="$1"
  root="$2"
  pattern="$3"
  echo "[$label]"
  if [ ! -d "$root" ]; then
    echo "  (missing directory)"
    return
  fi

  found=0
  for path in "$root"/$pattern; do
    [ -f "$path" ] || continue
    found=1
    size="$(stat -c %s "$path" 2>/dev/null || echo 0)"
    size_human="$(numfmt --to=iec --suffix=B "$size" 2>/dev/null || echo "${size}B")"
    mtime="$(stat -c %Y "$path" 2>/dev/null || echo 0)"
    echo "  $path | size=$size_human | mtime_epoch=$mtime"
  done

  if [ "$found" -eq 0 ]; then
    echo "  (no matching files)"
  fi
}

list_group "ranks" "/app/data/ingest/ranks" "boardgame_ranks_*"
list_group "game_data" "/app/data/ingest/game_data" "boardgame_data_*"
list_group "ratings" "/app/data/ingest/ratings" "boardgame_ratings_*"
EOF
)

fly ssh console -a "${APP_NAME}" -C "sh -lc '$REMOTE_CMD'"
