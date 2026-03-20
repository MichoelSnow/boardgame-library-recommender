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

require_var() {
  local name="$1"
  local value="${!name:-}"
  if [ -z "${value}" ]; then
    echo "Error: required env var ${name} is not set."
    exit 1
  fi
}

require_var "BGG_TOKEN"
require_var "BGG_RANKS_ZIP_URL"
require_var "INGEST_NOTIFY_EMAIL_TO"
require_var "INGEST_NOTIFY_EMAIL_FROM"

SMTP_HOST="${INGEST_NOTIFY_SMTP_HOST:-smtp-relay.brevo.com}"
SMTP_PORT="${INGEST_NOTIFY_SMTP_PORT:-587}"
SMTP_STARTTLS="${INGEST_NOTIFY_SMTP_STARTTLS:-true}"
SMTP_USERNAME="${INGEST_NOTIFY_SMTP_USERNAME:-${BREVO_SMTP_USERNAME:-${BREVO_SMTP_LOGIN:-}}}"
SMTP_PASSWORD="${INGEST_NOTIFY_SMTP_PASSWORD:-${BREVO_SMTP_PASSWORD:-${BREVO_SMTP_KEY:-}}}"

if [ -z "${SMTP_USERNAME}" ]; then
  echo "Error: set INGEST_NOTIFY_SMTP_USERNAME or BREVO_SMTP_USERNAME/BREVO_SMTP_LOGIN in .env."
  exit 1
fi
if [ -z "${SMTP_PASSWORD}" ]; then
  echo "Error: set INGEST_NOTIFY_SMTP_PASSWORD or BREVO_SMTP_PASSWORD/BREVO_SMTP_KEY in .env."
  exit 1
fi

echo "Setting ingest secrets for ${APP_NAME}"
fly secrets set \
  BGG_TOKEN="${BGG_TOKEN}" \
  BGG_RANKS_ZIP_URL="${BGG_RANKS_ZIP_URL}" \
  INGEST_NOTIFY_EMAIL_TO="${INGEST_NOTIFY_EMAIL_TO}" \
  INGEST_NOTIFY_EMAIL_FROM="${INGEST_NOTIFY_EMAIL_FROM}" \
  INGEST_NOTIFY_SMTP_HOST="${SMTP_HOST}" \
  INGEST_NOTIFY_SMTP_PORT="${SMTP_PORT}" \
  INGEST_NOTIFY_SMTP_STARTTLS="${SMTP_STARTTLS}" \
  INGEST_NOTIFY_SMTP_USERNAME="${SMTP_USERNAME}" \
  INGEST_NOTIFY_SMTP_PASSWORD="${SMTP_PASSWORD}" \
  -a "${APP_NAME}"
