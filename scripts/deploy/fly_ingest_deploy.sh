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

if ! command -v git >/dev/null 2>&1; then
  echo "Error: git is not installed or not on PATH."
  exit 1
fi

CONFIG_FILE="${1:-fly.ingest.toml}"
APP_NAME="${FLY_APP_NAME_INGEST:-bg-lib-ingest}"

if [ ! -f "${CONFIG_FILE}" ]; then
  echo "Error: config file '${CONFIG_FILE}' does not exist."
  exit 1
fi

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

git_sha="$(git rev-parse HEAD)"
build_timestamp="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"

echo "Deploying ${APP_NAME} using config=${CONFIG_FILE} with git_sha=${git_sha} build_timestamp=${build_timestamp}"

fly deploy \
  -c "${CONFIG_FILE}" \
  -a "${APP_NAME}" \
  --build-arg "GIT_SHA=${git_sha}" \
  --build-arg "BUILD_TIMESTAMP=${build_timestamp}"

if command -v jq >/dev/null 2>&1; then
  machine_id="$(
    fly machine list -a "${APP_NAME}" --json | jq -r '.[0].id // empty'
  )"
  if [ -n "${machine_id}" ]; then
    echo "Stopping machine ${machine_id} to keep deploy as image-update only."
    fly machine stop "${machine_id}" -a "${APP_NAME}" || true
  fi
fi

echo "Deploy step complete. Next steps:"
echo "  1) scripts/deploy/fly_ingest_set_secrets.sh"
echo "  2) scripts/deploy/fly_ingest_start.sh"
