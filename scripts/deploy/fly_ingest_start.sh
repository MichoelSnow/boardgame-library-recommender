#!/usr/bin/env bash

set -euo pipefail

SCRIPT_NAME="$(basename "$0" .sh)"
LOG_DIR="logs/deploy"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/${SCRIPT_NAME}_$(date -u +%Y%m%dT%H%M%SZ).log"
exec > >(tee -a "${LOG_FILE}") 2>&1
echo "Logging to ${LOG_FILE}"

if ! command -v fly >/dev/null 2>&1; then
  echo "Error: fly CLI is not installed or not on PATH."
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq is required."
  exit 1
fi

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

APP_NAME="${FLY_APP_NAME_INGEST:-bg-lib-ingest}"

machine_id="$(
  fly machine list -a "${APP_NAME}" --json | jq -r '.[0].id // empty'
)"

if [ -z "${machine_id}" ]; then
  echo "Error: no machine found for ${APP_NAME}. Deploy first using scripts/deploy/fly_ingest_deploy.sh"
  exit 1
fi

echo "Starting machine ${machine_id} for ${APP_NAME}"
fly machine start "${machine_id}" -a "${APP_NAME}"
