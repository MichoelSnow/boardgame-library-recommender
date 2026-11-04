#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 2 ]; then
  echo "Usage: $0 <dev|prod> <start|status|tail|log|stop>"
  exit 1
fi

ENV_NAME="$1"
ACTION="$2"

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

case "${ENV_NAME}" in
  dev)
    APP_NAME="${FLY_APP_NAME_DEV:-}"
    ;;
  prod)
    APP_NAME="${FLY_APP_NAME_PROD:-}"
    ;;
  *)
    echo "Invalid env: ${ENV_NAME}. Use dev or prod."
    exit 1
    ;;
esac

if [ -z "${APP_NAME}" ]; then
  echo "App name not set for ${ENV_NAME}. Check .env (FLY_APP_NAME_DEV/FLY_APP_NAME_PROD)."
  exit 1
fi

REMOTE_LOG_DIR="/data/logs/import_data"
LOCAL_WATCHER_DIR=".tmp/import_data_watchers"
LOCAL_WATCHER_PID_FILE="${LOCAL_WATCHER_DIR}/${APP_NAME}.pid"

get_machine_id() {
  fly machine list -a "${APP_NAME}" --json 2>/dev/null |
    jq -r 'map(select(.state == "started"))[0].id // .[0].id // empty'
}

set_machine_autostop() {
  local machine_id="$1"
  local mode="$2"
  if [ -z "${machine_id}" ]; then
    echo "Error: machine id is required to set autostop=${mode} on ${APP_NAME}." >&2
    return 1
  fi
  fly machine update "${machine_id}" -a "${APP_NAME}" --autostop="${mode}" --yes >/dev/null
  echo "Set autostop=${mode} on machine ${machine_id}"
}

get_current_autostop_mode() {
  local machine_id="$1"
  local machines_json
  local autostop_raw

  machines_json="$(fly machine list -a "${APP_NAME}" --json 2>/dev/null || true)"
  if [ -z "${machines_json}" ]; then
    echo "unknown"
    return 0
  fi

  autostop_raw="$(
    jq -r --arg id "${machine_id}" '
      (map(select(.id == $id))[0]) as $m
      | if ($m.config.services | type) == "array"
           and ($m.config.services | length) > 0
           and ($m.config.services[0] | has("autostop"))
        then ($m.config.services[0].autostop | tostring)
        else "unknown"
        end
    ' <<<"${machines_json}" 2>/dev/null || echo "unknown"
  )"

  case "${autostop_raw}" in
    true)
      echo "stop"
      ;;
    false)
      echo "off"
      ;;
    stop|off|suspend)
      echo "${autostop_raw}"
      ;;
    *)
      echo "unknown"
      ;;
  esac
}

ensure_machine_started() {
  local machine_id="$1"
  local machines_json
  local machine_state

  machines_json="$(fly machine list -a "${APP_NAME}" --json 2>/dev/null || true)"
  machine_state="$(
    jq -r --arg id "${machine_id}" '.[] | select(.id == $id) | .state' \
      <<<"${machines_json}" 2>/dev/null || true
  )"
  case "${machine_state}" in
    started|starting)
      ;;
    stopped|created|suspended)
      fly machine start "${machine_id}" -a "${APP_NAME}"
      ;;
    *)
      echo "Error: machine ${machine_id} has unexpected state '${machine_state:-unknown}'." >&2
      return 1
      ;;
  esac

  fly machine wait "${machine_id}" -a "${APP_NAME}" \
    --state started \
    --wait-timeout 5m
}

stop_local_autostop_restore_watcher() {
  local watcher_pid

  if [ ! -f "${LOCAL_WATCHER_PID_FILE}" ]; then
    return 0
  fi

  watcher_pid="$(cat "${LOCAL_WATCHER_PID_FILE}" 2>/dev/null || true)"
  if [ -n "${watcher_pid}" ] && kill -0 "${watcher_pid}" 2>/dev/null; then
    kill "${watcher_pid}" 2>/dev/null || true
    echo "stopped_autostop_restore_watcher pid=${watcher_pid}"
  fi
  rm -f "${LOCAL_WATCHER_PID_FILE}"
}

start_local_autostop_restore_watcher() {
  local machine_id="$1"
  local restore_mode="$2"
  local watched_pid="$3"
  local ts
  local watcher_log
  local watcher_script
  local watcher_pid

  mkdir -p "${LOCAL_WATCHER_DIR}"
  stop_local_autostop_restore_watcher

  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  watcher_log="${LOCAL_WATCHER_DIR}/${APP_NAME}_${ts}.log"
  watcher_script="${LOCAL_WATCHER_DIR}/${APP_NAME}_autostop_watcher.sh"

  cat > "${watcher_script}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

APP_NAME="$1"
MACHINE_ID="$2"
RESTORE_MODE="$3"
WATCHED_PID="$4"

restore_autostop() {
  fly machine update "${MACHINE_ID}" -a "${APP_NAME}" --autostop="${RESTORE_MODE}" --yes >/dev/null
  echo "restored_autostop=${RESTORE_MODE} machine=${MACHINE_ID} watched_pid=${WATCHED_PID}"
}

trap 'restore_autostop || echo "ERROR: unable to restore autostop=${RESTORE_MODE} machine=${MACHINE_ID}" >&2' EXIT

for _ in $(seq 1 960); do
  probe="$(
    fly ssh console -q -a "${APP_NAME}" -C \
      "sh -lc 'if kill -0 \"${WATCHED_PID}\" 2>/dev/null; then echo running=1; else echo running=0; fi'" \
      2>/dev/null || true
  )"

  if printf '%s\n' "${probe}" | grep -q '^running=0$'; then
    exit 0
  fi

  sleep 15
done

echo "watcher_timeout machine=${MACHINE_ID} watched_pid=${WATCHED_PID}"
exit 1
EOF

  chmod +x "${watcher_script}"
  nohup "${watcher_script}" "${APP_NAME}" "${machine_id}" "${restore_mode}" "${watched_pid}" > "${watcher_log}" 2>&1 &
  watcher_pid="$!"
  echo "${watcher_pid}" > "${LOCAL_WATCHER_PID_FILE}"
  echo "started_autostop_restore_watcher pid=${watcher_pid} restore_mode=${restore_mode} watched_pid=${watched_pid} log=${watcher_log}"
}

print_local_watcher_status() {
  local watcher_pid

  if [ ! -f "${LOCAL_WATCHER_PID_FILE}" ]; then
    echo "local_restore_watcher=none"
    return 0
  fi

  watcher_pid="$(cat "${LOCAL_WATCHER_PID_FILE}" 2>/dev/null || true)"
  if [ -n "${watcher_pid}" ] && kill -0 "${watcher_pid}" 2>/dev/null; then
    echo "local_restore_watcher=running pid=${watcher_pid}"
    return 0
  fi

  rm -f "${LOCAL_WATCHER_PID_FILE}"
  echo "local_restore_watcher=stopped"
}

print_machine_service_policy() {
  local machine_id="$1"
  local machines_json

  machines_json="$(fly machine list -a "${APP_NAME}" --json 2>/dev/null || true)"
  if [ -z "${machines_json}" ]; then
    echo "service_policy=unavailable"
    return 0
  fi

  if ! command -v jq >/dev/null 2>&1; then
    echo "service_policy=unavailable (jq not installed)"
    return 0
  fi

  if ! jq -e --arg id "${machine_id}" 'map(select(.id == $id)) | length > 0' >/dev/null 2>&1 <<<"${machines_json}"; then
    echo "service_policy=unavailable (machine id not found in list json)"
    return 0
  fi

  jq -r --arg id "${machine_id}" '
    (map(select(.id == $id))[0]) as $m
    | if ($m.config.services | type) == "array" and ($m.config.services | length) > 0 then
        $m.config.services
        | to_entries[]
        | "service[\(.key)] autostop=\(if (.value | has("autostop")) then (.value.autostop | tostring) else "unknown" end) autostart=\(if (.value | has("autostart")) then (.value.autostart | tostring) else "unknown" end) min_machines_running=\(if (.value | has("min_machines_running")) then (.value.min_machines_running | tostring) else "unknown" end)"
      else
        "service_policy=unavailable (no services configured)"
      end
  ' <<<"${machines_json}"
}

case "${ACTION}" in
  start)
    machine_id="$(get_machine_id || true)"
    if [ -z "${machine_id}" ]; then
      echo "Error: unable to resolve a machine id for ${APP_NAME}; refusing to start import." >&2
      exit 1
    fi

    previous_autostop_mode="$(get_current_autostop_mode "${machine_id}")"
    if [ "${previous_autostop_mode}" != "stop" ]; then
      echo "Error: expected ${APP_NAME} machine ${machine_id} to have autostop=stop; found ${previous_autostop_mode}." >&2
      echo "Correct the machine policy before starting an import." >&2
      exit 1
    fi

    set_machine_autostop "${machine_id}" off
    if ! ensure_machine_started "${machine_id}"; then
      echo "Error: machine did not reach started state; restoring autostop=${previous_autostop_mode}." >&2
      set_machine_autostop "${machine_id}" "${previous_autostop_mode}" || true
      exit 1
    fi
    TS="$(date -u +%Y%m%dT%H%M%SZ)"
    if ! start_output="$(fly ssh console -a "${APP_NAME}" -C "sh -lc 'mkdir -p \"${REMOTE_LOG_DIR}\"; PID_FILE=\"${REMOTE_LOG_DIR}/import_data.pid\"; LATEST_FILE=\"${REMOTE_LOG_DIR}/latest.log\"; LOG_FILE=\"${REMOTE_LOG_DIR}/import_data_${TS}.log\"; : > \"\${LOG_FILE}\"; rm -f \"\${PID_FILE}\"; cd /app/backend && nohup sh -lc \"set +e; poetry run alembic -c alembic.ini upgrade head && poetry run python app/import_data.py --delete-existing; rc=\\\$?; echo import_exit_code=\\\${rc}; rm -f \\\"\${PID_FILE}\\\"; exit \\\${rc}\" 2>&1 | tee -a \"\${LOG_FILE}\" /proc/1/fd/1 >/dev/null & echo \$! > \"\${PID_FILE}\" && ln -sf \"\${LOG_FILE}\" \"\${LATEST_FILE}\" && echo started pid=\$(cat \"\${PID_FILE}\") log=\${LOG_FILE}'")"; then
      echo "Error: unable to start the remote import; restoring autostop=${previous_autostop_mode}." >&2
      set_machine_autostop "${machine_id}" "${previous_autostop_mode}" || true
      exit 1
    fi
    echo "${start_output}"
    started_pid="$(printf '%s\n' "${start_output}" | sed -n 's/^started pid=\([0-9][0-9]*\).*/\1/p' | tail -n1)"
    if [ -z "${started_pid}" ]; then
      echo "Error: remote import did not return a process id; restoring autostop=${previous_autostop_mode}." >&2
      set_machine_autostop "${machine_id}" "${previous_autostop_mode}" || true
      exit 1
    fi
    start_local_autostop_restore_watcher "${machine_id}" "${previous_autostop_mode}" "${started_pid}"
    ;;
  status)
    status_output="$(fly ssh console -a "${APP_NAME}" -C "sh -lc 'PID_FILE=\"${REMOTE_LOG_DIR}/import_data.pid\"; LATEST_FILE=\"${REMOTE_LOG_DIR}/latest.log\"; if [ -s \"\${PID_FILE}\" ]; then pid=\$(cat \"\${PID_FILE}\"); if kill -0 \"\$pid\" 2>/dev/null; then echo running pid=\$pid; else echo not_running pid=\$pid; fi; else echo no_pid_file; fi; if [ -L \"\${LATEST_FILE}\" ] && [ -f \"\$(readlink -f \"\${LATEST_FILE}\")\" ]; then echo latest_log=\$(readlink -f \"\${LATEST_FILE}\"); else fallback=\$(ls -1t ${REMOTE_LOG_DIR}/import_data_*.log 2>/dev/null | head -n1 || true); [ -n \"\${fallback}\" ] && echo latest_log=\${fallback} || echo no_log_file; fi'")"
    echo "${status_output}"
    machine_id="$(get_machine_id || true)"
    if [ -n "${machine_id}" ]; then
      echo "machine_id=${machine_id}"
      print_machine_service_policy "${machine_id}"
    else
      echo "machine_id=unavailable"
      echo "service_policy=unavailable"
    fi
    print_local_watcher_status
    ;;
  tail)
    fly ssh console -a "${APP_NAME}" -C "sh -lc 'LATEST_FILE=\"${REMOTE_LOG_DIR}/latest.log\"; if [ -L \"\${LATEST_FILE}\" ] && [ -f \"\$(readlink -f \"\${LATEST_FILE}\")\" ]; then target=\"\$(readlink -f \"\${LATEST_FILE}\")\"; else target=\$(ls -1t ${REMOTE_LOG_DIR}/import_data_*.log 2>/dev/null | head -n1 || true); fi; [ -n \"\${target}\" ] || { echo no_latest_log; exit 1; }; echo tailing=\${target}; tail -n 200 -f \"\${target}\"'"
    ;;
  log)
    LOCAL_LOG_DIR="logs/import_data"
    mkdir -p "${LOCAL_LOG_DIR}"
    LOCAL_LOG_FILE="${LOCAL_LOG_DIR}/${APP_NAME}_import_data_latest_$(date -u +%Y%m%dT%H%M%SZ).log"
    fly ssh console -q -a "${APP_NAME}" -C "sh -lc 'LATEST_FILE=\"${REMOTE_LOG_DIR}/latest.log\"; if [ -L \"\${LATEST_FILE}\" ] && [ -f \"\$(readlink -f \"\${LATEST_FILE}\")\" ]; then target=\"\$(readlink -f \"\${LATEST_FILE}\")\"; else target=\$(ls -1t ${REMOTE_LOG_DIR}/import_data_*.log 2>/dev/null | head -n1 || true); fi; [ -n \"\${target}\" ] || { echo no_latest_log; exit 1; }; echo source_log=\${target}; cat \"\${target}\"'" > "${LOCAL_LOG_FILE}"
    echo "downloaded_log=${LOCAL_LOG_FILE}"
    ;;
  stop)
    stop_local_autostop_restore_watcher
    machine_id="$(get_machine_id || true)"
    if [ -z "${machine_id}" ]; then
      echo "Error: unable to resolve a machine id for ${APP_NAME}; autostop was not changed." >&2
      exit 1
    fi
    if ! fly ssh console -a "${APP_NAME}" -C "sh -lc 'PID_FILE=\"${REMOTE_LOG_DIR}/import_data.pid\"; if [ -s \"\${PID_FILE}\" ]; then pid=\$(cat \"\${PID_FILE}\"); if kill -0 \"\$pid\" 2>/dev/null; then kill \"\$pid\" && echo stopped pid=\$pid; else echo not_running pid=\$pid; fi; else echo no_pid_file; fi'"; then
      echo "Warning: unable to contact the machine; restoring autostop anyway." >&2
    fi
    set_machine_autostop "${machine_id}" stop
    ;;
  *)
    echo "Invalid action: ${ACTION}. Use start, status, tail, log, or stop."
    exit 1
    ;;
esac
