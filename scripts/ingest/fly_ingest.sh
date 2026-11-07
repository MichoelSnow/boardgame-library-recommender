#!/usr/bin/env bash

set -euo pipefail

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

APP_NAME="${FLY_APP_NAME_INGEST:-bg-lib-ingest}"
PIPELINE_COMMAND="bash scripts/ingest/run_container.sh poetry run python scripts/data_pipeline/run_ingest_pipeline.py"
STATE_PATH="/app/data/ingest/run_state.json"
DEFAULT_MAINTENANCE_DURATION="${INGEST_MAINTENANCE_DEFAULT_DURATION:-4h}"
MAX_MAINTENANCE_DURATION_SECONDS="${INGEST_MAINTENANCE_MAX_DURATION_SECONDS:-43200}"

usage() {
  cat <<'EOF'
Usage:
  scripts/ingest/fly_ingest.sh maintenance start [--for <duration>]
  scripts/ingest/fly_ingest.sh maintenance stop|status
  scripts/ingest/fly_ingest.sh machine status|shell
  scripts/ingest/fly_ingest.sh run ranks|game-data|ratings|fresh|resume
  scripts/ingest/fly_ingest.sh deploy
  scripts/ingest/fly_ingest.sh secrets sync
  scripts/ingest/fly_ingest.sh resize --memory <mb>
  scripts/ingest/fly_ingest.sh logs
  scripts/ingest/fly_ingest.sh artifacts list
  scripts/ingest/fly_ingest.sh artifacts download [options]
EOF
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Error: required command '$1' is not installed." >&2
    exit 1
  }
}

require_command fly
require_command jq

machine_id() {
  fly machine list -a "$APP_NAME" --json |
    jq -r 'map(select(.state == "started"))[0].id // .[0].id // empty'
}

machine_state() {
  local id
  id="$(machine_id)"
  [ -n "$id" ] || return 1
  fly machine list -a "$APP_NAME" --json |
    jq -r --arg id "$id" '.[] | select(.id == $id) | .state'
}

maintenance_secret_set() {
  fly secrets list -a "$APP_NAME" --json |
    jq -e 'any(.[]; ((.Name // .name) == "INGEST_MAINTENANCE_MODE"))' \
    >/dev/null 2>&1
}

maintenance_value() {
  if [ "$(machine_state 2>/dev/null || true)" != "started" ]; then
    if maintenance_secret_set; then
      echo "true"
    else
      echo "false"
    fi
    return 0
  fi
  fly ssh console -q -a "$APP_NAME" -C \
    "sh -lc 'printf \"%s\\n\" \"\${INGEST_MAINTENANCE_MODE:-false}\"'"
}

maintenance_duration_seconds() {
  local duration="${1:-}"
  local amount multiplier
  case "$duration" in
    *m)
      amount="${duration%m}"
      multiplier=60
      ;;
    *h)
      amount="${duration%h}"
      multiplier=3600
      ;;
    *d)
      amount="${duration%d}"
      multiplier=86400
      ;;
    *)
      echo "Error: maintenance duration must use m, h, or d (for example 30m or 4h)." >&2
      exit 1
      ;;
  esac
  [[ "$amount" =~ ^[1-9][0-9]*$ ]] || {
    echo "Error: maintenance duration must be a positive value (for example 4h)." >&2
    exit 1
  }
  local seconds=$((10#$amount * multiplier))
  if [ "$seconds" -gt "$MAX_MAINTENANCE_DURATION_SECONDS" ]; then
    echo "Error: maintenance duration cannot exceed ${MAX_MAINTENANCE_DURATION_SECONDS} seconds." >&2
    exit 1
  fi
  echo "$seconds"
}

maintenance_until() {
  local duration_seconds="$1"
  local now_epoch
  now_epoch="$(date -u +%s)"
  date -u -d "@$((now_epoch + duration_seconds))" +%Y-%m-%dT%H:%M:%SZ
}

run_state_is_active() {
  [ "$(machine_state 2>/dev/null || true)" = "started" ] || return 1
  [ "$(maintenance_value)" != "true" ] || return 1
  fly ssh console -q -a "$APP_NAME" -C \
    "sh -lc 'grep -q '\''\"status\": \"running\"'\'' $STATE_PATH'" \
    >/dev/null 2>&1
}

set_machine_command() {
  local id="$1"
  local command="$2"
  local attempt
  for attempt in 1 2 3 4 5; do
    if fly machine update "$id" -a "$APP_NAME" --command "$command" --skip-start --yes \
      >/dev/null 2>&1; then
      return 0
    fi
    if [ "$attempt" -lt 5 ]; then
      sleep 3
    fi
  done
  echo "Error: machine remained busy while updating its command." >&2
  exit 1
}

wait_for_machine_settled() {
  local id="$1"
  fly machine wait "$id" -a "$APP_NAME" --state settled --wait-timeout 5m \
    >/dev/null
}

maintenance_start() {
  local duration="${1:-$DEFAULT_MAINTENANCE_DURATION}"
  local duration_seconds until id state maintenance
  duration_seconds="$(maintenance_duration_seconds "$duration")"
  until="$(maintenance_until "$duration_seconds")"
  id="$(machine_id)"
  [ -n "$id" ] || {
    echo "Error: no machine exists for $APP_NAME." >&2
    exit 1
  }
  state="$(machine_state || true)"
  if [ "$state" = "started" ]; then
    maintenance="$(maintenance_value)"
    if [ "$maintenance" = "true" ]; then
      echo "Maintenance mode is already active on machine $id."
      return 0
    fi
    if run_state_is_active; then
      echo "Error: an ingest run is active; maintenance mode cannot start." >&2
      exit 1
    fi
    echo "Error: machine $id is already running; stop it before starting maintenance mode." >&2
    exit 1
  fi
  set_machine_command "$id" "$PIPELINE_COMMAND"
  fly secrets set \
    INGEST_MAINTENANCE_MODE=true \
    INGEST_MAINTENANCE_UNTIL_UTC="$until" \
    -a "$APP_NAME" >/dev/null
  wait_for_machine_settled "$id"
  fly machine start "$id" -a "$APP_NAME"
  echo "Maintenance mode started on machine $id until $until."
}

maintenance_stop() {
  local id state
  id="$(machine_id)"
  [ -n "$id" ] || {
    fly secrets unset INGEST_MAINTENANCE_MODE INGEST_MAINTENANCE_UNTIL_UTC \
      -a "$APP_NAME" >/dev/null || true
    echo "Maintenance mode is disabled; no machine exists."
    return 0
  }
  state="$(machine_state || true)"
  if [ "$state" = "started" ] && run_state_is_active; then
    echo "Error: an ingest run is active; maintenance mode cannot stop it." >&2
    exit 1
  fi
  if [ "$state" = "started" ]; then
    fly machine stop "$id" -a "$APP_NAME"
  fi
  fly secrets unset INGEST_MAINTENANCE_MODE INGEST_MAINTENANCE_UNTIL_UTC \
    -a "$APP_NAME" >/dev/null || true
  echo "Maintenance mode stopped; machine is stopped."
}

maintenance_status() {
  local state maintenance
  state="$(machine_state 2>/dev/null || true)"
  maintenance="$(maintenance_value)"
  echo "app=$APP_NAME"
  echo "machine_state=${state:-absent}"
  echo "maintenance=$maintenance"
}

machine_status() {
  fly machine list -a "$APP_NAME"
  maintenance_status
}

machine_shell() {
  if [ "$(machine_state 2>/dev/null || true)" != "started" ] || \
    [ "$(maintenance_value)" != "true" ]; then
    echo "Error: start maintenance mode before opening a shell." >&2
    exit 1
  fi
  fly ssh console -a "$APP_NAME"
}

require_run_ready() {
  local state maintenance
  state="$(machine_state 2>/dev/null || true)"
  if [ "$state" != "started" ] && maintenance_secret_set; then
    echo "Clearing the expired or stopped maintenance lease before starting a run."
    fly secrets unset INGEST_MAINTENANCE_MODE INGEST_MAINTENANCE_UNTIL_UTC \
      -a "$APP_NAME" >/dev/null || true
  fi
  maintenance="$(maintenance_value)"
  if [ "$maintenance" = "true" ]; then
    echo "Error: maintenance mode is active; run maintenance stop first." >&2
    exit 1
  fi
  if [ "$state" = "started" ]; then
    echo "Error: machine is already running an ingest command." >&2
    exit 1
  fi
}

start_run() {
  local command="$1"
  local id
  require_run_ready
  id="$(machine_id)"
  [ -n "$id" ] || {
    echo "Error: no machine exists for $APP_NAME." >&2
    exit 1
  }
  if maintenance_secret_set; then
    fly secrets unset INGEST_MAINTENANCE_MODE INGEST_MAINTENANCE_UNTIL_UTC \
      -a "$APP_NAME" >/dev/null
    wait_for_machine_settled "$id"
  fi
  set_machine_command "$id" "$command"
  fly machine start "$id" -a "$APP_NAME"
  echo "Started detached ingest command on machine $id."
}

run_command() {
  case "$1" in
    ranks)
      start_run "$PIPELINE_COMMAND --only-stage get_ranks"
      ;;
    game-data)
      start_run "$PIPELINE_COMMAND --only-stage get_game_data"
      ;;
    ratings)
      start_run "$PIPELINE_COMMAND --only-stage get_ratings"
      ;;
    fresh)
      start_run "$PIPELINE_COMMAND --reset-state"
      ;;
    resume)
      start_run "$PIPELINE_COMMAND"
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

resize_machine() {
  [ "${1:-}" = "--memory" ] && [ -n "${2:-}" ] || {
    echo "Usage: $0 resize --memory <mb>" >&2
    exit 1
  }
  local id
  id="$(machine_id)"
  fly machine update "$id" -a "$APP_NAME" --vm-memory "$2" --skip-start --yes
}

capture_logs() {
  local log_dir="logs/deploy"
  local log_path
  local id
  mkdir -p "$log_dir"
  log_path="${log_dir}/fly_ingest_logs_$(date -u +%Y%m%dT%H%M%SZ).log"
  id="$(machine_id 2>/dev/null || true)"
  if [ -n "$id" ]; then
    fly logs --no-tail -a "$APP_NAME" --machine "$id" >"$log_path" 2>&1
  else
    fly logs --no-tail -a "$APP_NAME" >"$log_path" 2>&1
  fi
  echo "Wrote Fly logs to $log_path"
}

main() {
  case "${1:-}" in
    maintenance)
      case "${2:-}" in
        start)
          shift 2
          case "${1:-}" in
            "") maintenance_start ;;
            --for)
              [ -n "${2:-}" ] && [ -z "${3:-}" ] || { usage; exit 1; }
              maintenance_start "$2"
              ;;
            *) usage; exit 1 ;;
          esac
          ;;
        stop) maintenance_stop ;;
        status) maintenance_status ;;
        *) usage; exit 1 ;;
      esac
      ;;
    machine)
      case "${2:-}" in
        status) machine_status ;;
        shell) machine_shell ;;
        *) usage; exit 1 ;;
      esac
      ;;
    run)
      run_command "${2:-}"
      ;;
    deploy) scripts/deploy/fly_ingest_deploy.sh ;;
    secrets)
      [ "${2:-}" = "sync" ] || { usage; exit 1; }
      scripts/deploy/fly_ingest_set_secrets.sh
      ;;
    resize) resize_machine "${2:-}" "${3:-}" ;;
    logs) capture_logs ;;
    artifacts)
      case "${2:-}" in
        list) scripts/deploy/fly_ingest_list_artifacts.sh ;;
        download) shift 2; scripts/deploy/fly_ingest_download_artifact.sh "$@" ;;
        *) usage; exit 1 ;;
      esac
      ;;
    -h|--help|"") usage ;;
    *) usage; exit 1 ;;
  esac
}

main "$@"
