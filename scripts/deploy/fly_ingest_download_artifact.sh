#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

SCRIPT_NAME="$(basename "$0" .sh)"
LOG_DIR="logs/deploy"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/${SCRIPT_NAME}_$(date -u +%Y%m%dT%H%M%SZ).log"
exec > >(tee -a "${LOG_FILE}") 2>&1
echo "Logging to ${LOG_FILE}"

usage() {
  cat <<'EOF'
Usage:
  scripts/deploy/fly_ingest_download_artifact.sh \
    --remote-path <remote_file> \
    [--output-dir <dir>] [--chunk-mb <mb>] [--keep-parts] [--overwrite]

The transfer is resumable by chunk files and is finalized only after size and
SHA-256 verification. By default, verified transfers remove their chunk cache.
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

if ! command -v fly >/dev/null 2>&1; then
  echo "Error: fly CLI is not installed or not on PATH." >&2
  exit 1
fi

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

APP_NAME="${FLY_APP_NAME_INGEST:-bg-lib-ingest}"
exec python3 "${REPO_ROOT}/scripts/ingest/artifact_export.py" \
  --backend fly \
  --app "${APP_NAME}" \
  "$@"
