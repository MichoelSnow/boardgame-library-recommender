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
  local machine_id
  machine_id="$(fly machine list -a "${APP_NAME}" --json 2>/dev/null | jq -r 'map(select(.state == "started"))[0].id // .[0].id // empty' || true)"
  if [ -n "${machine_id}" ]; then
    echo "${machine_id}"
    return 0
  fi
  machine_id="$(fly machine list -a "${APP_NAME}" 2>/dev/null | awk 'NR>3 && $1 ~ /^[0-9a-f]+$/ {print $1; exit}' || true)"
  if [ -n "${machine_id}" ]; then
    echo "${machine_id}"
    return 0
  fi
  return 1
}

set_machine_autostop() {
  local mode="$1"
  local machine_id
  machine_id="$(get_machine_id || true)"
  if [ -z "${machine_id}" ]; then
    echo "Warning: unable to resolve machine id for ${APP_NAME}; skipping autostop=${mode} update."
    return 0
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
REMOTE_LOG_DIR="$5"
PID_FILE="${REMOTE_LOG_DIR}/import_data.pid"

for _ in $(seq 1 960); do
  probe="$(
    fly ssh console -q -a "${APP_NAME}" -C \
      "sh -lc 'PID_FILE=\"${PID_FILE}\"; WATCHED_PID=\"${WATCHED_PID}\"; current=\"\"; [ -s \"\${PID_FILE}\" ] && current=\$(cat \"\${PID_FILE}\"); if [ -n \"\${current}\" ] && [ \"\${current}\" != \"\${WATCHED_PID}\" ]; then echo superseded current_pid=\${current}; exit 0; fi; if kill -0 \"\${WATCHED_PID}\" 2>/dev/null; then echo running=1 current_pid=\${current}; else echo running=0 current_pid=\${current}; fi'" \
      2>/dev/null || true
  )"

  if printf '%s\n' "${probe}" | grep -q '^superseded '; then
    echo "watcher_exit reason=superseded watched_pid=${WATCHED_PID}"
    exit 0
  fi

  if printf '%s\n' "${probe}" | grep -q '^running=0 '; then
    fly machine update "${MACHINE_ID}" -a "${APP_NAME}" --autostop="${RESTORE_MODE}" --yes >/dev/null
    echo "restored_autostop=${RESTORE_MODE} machine=${MACHINE_ID} watched_pid=${WATCHED_PID}"
    exit 0
  fi

  sleep 15
done

echo "watcher_timeout machine=${MACHINE_ID} watched_pid=${WATCHED_PID}"
exit 1
EOF

  chmod +x "${watcher_script}"
  nohup "${watcher_script}" "${APP_NAME}" "${machine_id}" "${restore_mode}" "${watched_pid}" "${REMOTE_LOG_DIR}" > "${watcher_log}" 2>&1 &
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
    previous_autostop_mode="stop"
    if [ -n "${machine_id}" ]; then
      previous_autostop_mode="$(get_current_autostop_mode "${machine_id}")"
      if [ "${previous_autostop_mode}" = "unknown" ]; then
        previous_autostop_mode="stop"
        echo "warning: unable to read prior autostop mode; defaulting restore mode to stop"
      fi
    else
      echo "warning: unable to resolve machine id before start; autostop restore watcher disabled for this run"
    fi

    set_machine_autostop off
    TS="$(date -u +%Y%m%dT%H%M%SZ)"
    start_output="$(fly ssh console -a "${APP_NAME}" -C "sh -lc 'mkdir -p \"${REMOTE_LOG_DIR}\"; PID_FILE=\"${REMOTE_LOG_DIR}/import_data.pid\"; LATEST_FILE=\"${REMOTE_LOG_DIR}/latest.log\"; LOG_FILE=\"${REMOTE_LOG_DIR}/import_data_${TS}.log\"; : > \"\${LOG_FILE}\"; rm -f \"\${PID_FILE}\"; cd /app/backend && nohup sh -lc \"set +e; poetry run alembic -c alembic.ini upgrade head && poetry run python app/import_data.py --delete-existing; rc=\\\$?; echo import_exit_code=\\\${rc}; rm -f \\\"\${PID_FILE}\\\"; exit \\\${rc}\" 2>&1 | tee -a \"\${LOG_FILE}\" /proc/1/fd/1 >/dev/null & echo \$! > \"\${PID_FILE}\" && ln -sf \"\${LOG_FILE}\" \"\${LATEST_FILE}\" && echo started pid=\$(cat \"\${PID_FILE}\") log=\${LOG_FILE}'")"
    echo "${start_output}"
    started_pid="$(printf '%s\n' "${start_output}" | sed -n 's/^started pid=\([0-9][0-9]*\).*/\1/p' | tail -n1)"
    if [ -n "${machine_id}" ] && [ -n "${started_pid}" ]; then
      start_local_autostop_restore_watcher "${machine_id}" "${previous_autostop_mode}" "${started_pid}"
    else
      echo "warning: unable to start autostop restore watcher (machine_id=${machine_id:-missing}, pid=${started_pid:-missing})"
    fi
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
    fly ssh console -a "${APP_NAME}" -C "sh -lc 'PID_FILE=\"${REMOTE_LOG_DIR}/import_data.pid\"; if [ -s \"\${PID_FILE}\" ]; then pid=\$(cat \"\${PID_FILE}\"); if kill -0 \"\$pid\" 2>/dev/null; then kill \"\$pid\" && echo stopped pid=\$pid; else echo not_running pid=\$pid; fi; else echo no_pid_file; fi'"
    set_machine_autostop stop
    ;;
  *)
    echo "Invalid action: ${ACTION}. Use start, status, tail, log, or stop."
    exit 1
    ;;
esac
