#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 2 ]; then
  echo "Usage: $0 <dev|prod> <start|status|tail|stop>"
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

case "${ACTION}" in
  start)
    TS="$(date -u +%Y%m%dT%H%M%SZ)"
    fly ssh console -a "${APP_NAME}" -C "sh -lc 'mkdir -p \"${REMOTE_LOG_DIR}\"; PID_FILE=\"${REMOTE_LOG_DIR}/import_data.pid\"; LATEST_FILE=\"${REMOTE_LOG_DIR}/latest.log\"; LOG_FILE=\"${REMOTE_LOG_DIR}/import_data_${TS}.log\"; : > \"\${LOG_FILE}\"; cd /app/backend && nohup sh -lc \"(poetry run alembic -c alembic.ini upgrade head && poetry run python app/import_data.py --delete-existing) 2>&1 | tee -a \\\"\\\${LOG_FILE}\\\" > /proc/1/fd/1\" </dev/null >/dev/null 2>&1 & echo \$! > \"\${PID_FILE}\" && ln -sf \"\${LOG_FILE}\" \"\${LATEST_FILE}\" && echo started pid=\$(cat \"\${PID_FILE}\") log=\${LOG_FILE}'"
    ;;
  status)
    fly ssh console -a "${APP_NAME}" -C "sh -lc 'PID_FILE=\"${REMOTE_LOG_DIR}/import_data.pid\"; LATEST_FILE=\"${REMOTE_LOG_DIR}/latest.log\"; if [ -s \"\${PID_FILE}\" ]; then pid=\$(cat \"\${PID_FILE}\"); if kill -0 \"\$pid\" 2>/dev/null; then echo running pid=\$pid; else echo not_running pid=\$pid; fi; else echo no_pid_file; fi; if [ -L \"\${LATEST_FILE}\" ] && [ -f \"\$(readlink -f \"\${LATEST_FILE}\")\" ]; then echo latest_log=\$(readlink -f \"\${LATEST_FILE}\"); else fallback=\$(ls -1t ${REMOTE_LOG_DIR}/import_data_*.log 2>/dev/null | head -n1 || true); [ -n \"\${fallback}\" ] && echo latest_log=\${fallback} || echo no_log_file; fi'"
    ;;
  tail)
    fly ssh console -a "${APP_NAME}" -C "sh -lc 'LATEST_FILE=\"${REMOTE_LOG_DIR}/latest.log\"; if [ -L \"\${LATEST_FILE}\" ] && [ -f \"\$(readlink -f \"\${LATEST_FILE}\")\" ]; then target=\"\$(readlink -f \"\${LATEST_FILE}\")\"; else target=\$(ls -1t ${REMOTE_LOG_DIR}/import_data_*.log 2>/dev/null | head -n1 || true); fi; [ -n \"\${target}\" ] || { echo no_latest_log; exit 1; }; echo tailing=\${target}; tail -n 200 -f \"\${target}\"'"
    ;;
  stop)
    fly ssh console -a "${APP_NAME}" -C "sh -lc 'PID_FILE=\"${REMOTE_LOG_DIR}/import_data.pid\"; if [ -s \"\${PID_FILE}\" ]; then pid=\$(cat \"\${PID_FILE}\"); if kill -0 \"\$pid\" 2>/dev/null; then kill \"\$pid\" && echo stopped pid=\$pid; else echo not_running pid=\$pid; fi; else echo no_pid_file; fi'"
    ;;
  *)
    echo "Invalid action: ${ACTION}. Use start, status, tail, or stop."
    exit 1
    ;;
esac
