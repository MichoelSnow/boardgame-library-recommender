#!/usr/bin/env bash

set -euo pipefail

if [ "$#" -eq 0 ]; then
  echo "Error: a container command is required." >&2
  exit 2
fi

export INGEST_RUN_ID="${INGEST_RUN_ID:-$(python -c 'import uuid; print(uuid.uuid4())')}"
LOCK_COMMAND=(poetry run python scripts/ingest/runtime_lock.py)

"${LOCK_COMMAND[@]}" acquire

release_lock() {
  "${LOCK_COMMAND[@]}" release || {
    echo "Warning: unable to release ingestion workspace ownership." >&2
  }
}

trap release_lock EXIT

set +e
"$@"
exit_code=$?
set -e
exit "$exit_code"
