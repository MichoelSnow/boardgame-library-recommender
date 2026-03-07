#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/fly_stack.sh <dev|prod> <up|down|status>

Commands:
  up      Start DB machine first, then app machine.
  down    Stop app machine first, then DB machine.
  status  Show machine status for app + DB.

Notes:
  - Fly does not provide native cross-app machine dependency linking.
  - This script is the safe operational sequence for app/db stacks.
EOF
}

if [ "$#" -ne 2 ]; then
  usage
  exit 1
fi

environment="$1"
action="$2"

case "${environment}" in
  dev)
    app_name="pax-tt-app-dev"
    db_name="pax-tt-db-dev"
    ;;
  prod)
    app_name="pax-tt-app"
    db_name="pax-tt-db-prod"
    ;;
  *)
    usage
    exit 1
    ;;
esac

if ! command -v fly >/dev/null 2>&1; then
  echo "Error: fly CLI is not installed or not on PATH."
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq is required for scripts/fly_stack.sh."
  exit 1
fi

first_machine_id() {
  local app="$1"
  fly machines list -a "${app}" --json | jq -r '.[0].id // empty'
}

start_machine_if_present() {
  local app="$1"
  local id
  id="$(first_machine_id "${app}")"
  if [ -z "${id}" ]; then
    echo "No machine found for ${app}. Deploy to create one before starting."
    return 1
  fi
  echo "Starting ${app} machine ${id}"
  fly machine start "${id}" -a "${app}"
}

stop_machine_if_present() {
  local app="$1"
  local id
  id="$(first_machine_id "${app}")"
  if [ -z "${id}" ]; then
    echo "No machine found for ${app}; nothing to stop."
    return 0
  fi
  echo "Stopping ${app} machine ${id}"
  fly machine stop "${id}" -a "${app}"
}

show_status() {
  echo
  echo "=== ${db_name} ==="
  fly machines list -a "${db_name}"
  echo
  echo "=== ${app_name} ==="
  fly machines list -a "${app_name}"
}

case "${action}" in
  up)
    # Safe startup order for dependent stack.
    start_machine_if_present "${db_name}"
    start_machine_if_present "${app_name}"
    show_status
    ;;
  down)
    # Safe shutdown order for dependent stack.
    stop_machine_if_present "${app_name}"
    stop_machine_if_present "${db_name}"
    show_status
    ;;
  status)
    show_status
    ;;
  *)
    usage
    exit 1
    ;;
esac
