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

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

APP_NAME="${FLY_APP_NAME_INGEST:-bg-lib-ingest}"
STATE_PATH="${INGEST_RUN_STATE_PATH:-/app/data/ingest/run_state.json}"

echo "Machine status for ${APP_NAME}:"
machine_list_output="$(fly machine list -a "${APP_NAME}")"
echo "${machine_list_output}"

machine_line="$(
  printf '%s\n' "${machine_list_output}" | awk 'length($1) > 8 && $1 ~ /^[0-9a-f]+$/ {print; exit}'
)"
machine_id="$(printf '%s\n' "${machine_line}" | awk '{print $1}')"
machine_state="$(printf '%s\n' "${machine_line}" | awk '{print $3}')"

if [ -z "${machine_id}" ]; then
  echo "No machine found."
  exit 0
fi

if [ "${machine_state}" != "started" ]; then
  echo "Machine is '${machine_state}'. State file not queried."
  exit 0
fi

echo
echo "Current ingest run state (${STATE_PATH}):"
fly ssh console -a "${APP_NAME}" -C "cat ${STATE_PATH}" || true
