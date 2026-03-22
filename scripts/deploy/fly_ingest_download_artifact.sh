#!/usr/bin/env bash

set -euo pipefail

SCRIPT_NAME="$(basename "$0" .sh)"
LOG_DIR="logs/deploy"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/${SCRIPT_NAME}_$(date -u +%Y%m%dT%H%M%SZ).log"
exec > >(tee -a "${LOG_FILE}") 2>&1
echo "Logging to ${LOG_FILE}"

usage() {
  cat <<'EOF'
Usage:
  scripts/deploy/fly_ingest_download_artifact.sh --remote-path <remote_file> [--output-dir <dir>] [--chunk-mb <mb>] [--keep-parts]

Example:
  scripts/deploy/fly_ingest_download_artifact.sh \
    --remote-path /app/data/ingest/game_data/boardgame_data_1742490000.duckdb \
    --chunk-mb 64

Notes:
- Download is resumable by chunk files (.parts directory).
- Script verifies SHA-256 against the remote file before finalizing.
- By default, .parts are removed after a successful verified download.
- Use --keep-parts to retain chunk cache.
- If --output-dir is omitted, destination is auto-selected by remote path:
  - /app/data/ingest/ranks/* -> data/ingest/ranks
  - /app/data/ingest/game_data/* -> data/ingest/game_data
  - /app/data/ingest/ratings/* -> data/ingest/ratings
EOF
}

if ! command -v fly >/dev/null 2>&1; then
  echo "Error: fly CLI is not installed or not on PATH."
  exit 1
fi

if ! command -v sha256sum >/dev/null 2>&1; then
  echo "Error: sha256sum is required."
  exit 1
fi

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

APP_NAME="${FLY_APP_NAME_INGEST:-bg-lib-ingest}"
OUTPUT_DIR=""
CHUNK_MB=64
REMOTE_PATH=""
KEEP_PARTS=0

while [ $# -gt 0 ]; do
  case "$1" in
    --remote-path)
      REMOTE_PATH="$2"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --chunk-mb)
      CHUNK_MB="$2"
      shift 2
      ;;
    --keep-parts)
      KEEP_PARTS=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Error: unknown argument '$1'"
      usage
      exit 1
      ;;
  esac
done

if [ -z "${REMOTE_PATH}" ]; then
  echo "Error: --remote-path is required."
  usage
  exit 1
fi

case "${CHUNK_MB}" in
  ''|*[!0-9]*)
    echo "Error: --chunk-mb must be a positive integer."
    exit 1
    ;;
esac
if [ "${CHUNK_MB}" -le 0 ]; then
  echo "Error: --chunk-mb must be > 0."
  exit 1
fi

if [ -z "${OUTPUT_DIR}" ]; then
  case "${REMOTE_PATH}" in
    /app/data/ingest/ranks/*)
      OUTPUT_DIR="data/ingest/ranks"
      ;;
    /app/data/ingest/game_data/*)
      OUTPUT_DIR="data/ingest/game_data"
      ;;
    /app/data/ingest/ratings/*)
      OUTPUT_DIR="data/ingest/ratings"
      ;;
    *)
      OUTPUT_DIR="data/ingest/downloads"
      ;;
  esac
fi

mkdir -p "${OUTPUT_DIR}"
base_name="$(basename "${REMOTE_PATH}")"
local_file="${OUTPUT_DIR}/${base_name}"
parts_dir="${OUTPUT_DIR}/.${base_name}.parts"
mkdir -p "${parts_dir}"

echo "App: ${APP_NAME}"
echo "Remote file: ${REMOTE_PATH}"
echo "Local file: ${local_file}"
echo "Chunk size: ${CHUNK_MB} MB"

remote_size="$(fly ssh console -a "${APP_NAME}" -C "stat -c %s '${REMOTE_PATH}'" | tr -d '\r' | tail -n1)"
case "${remote_size}" in
  ''|*[!0-9]*)
    echo "Error: could not determine remote file size for '${REMOTE_PATH}'."
    exit 1
    ;;
esac
if [ "${remote_size}" -le 0 ]; then
  echo "Error: remote file size is zero."
  exit 1
fi

chunk_bytes=$((CHUNK_MB * 1024 * 1024))
chunk_count=$(( (remote_size + chunk_bytes - 1) / chunk_bytes ))
echo "Remote size: ${remote_size} bytes (${chunk_count} chunks)"

download_chunk() {
  chunk_index="$1"
  part_file="$(printf "%s/part_%06d.bin" "${parts_dir}" "${chunk_index}")"
  temp_file="${part_file}.tmp"

  offset_bytes=$((chunk_index * chunk_bytes))
  remaining=$((remote_size - offset_bytes))
  if [ "${remaining}" -le 0 ]; then
    return
  fi

  expected_size="${chunk_bytes}"
  if [ "${remaining}" -lt "${chunk_bytes}" ]; then
    expected_size="${remaining}"
  fi

  if [ -f "${part_file}" ]; then
    existing_size="$(stat -c %s "${part_file}")"
    if [ "${existing_size}" -eq "${expected_size}" ]; then
      echo "Chunk ${chunk_index}/${chunk_count} already present (${existing_size} bytes), skipping."
      return
    fi
    echo "Chunk ${chunk_index}/${chunk_count} has wrong size (${existing_size} != ${expected_size}), re-downloading."
    rm -f "${part_file}"
  fi

  echo "Downloading chunk ${chunk_index}/${chunk_count}..."
  count_mb=$(( (expected_size + 1024 * 1024 - 1) / (1024 * 1024) ))
  fly ssh console -a "${APP_NAME}" -C \
    "dd if='${REMOTE_PATH}' bs=1M skip=$((chunk_index * CHUNK_MB)) count=${count_mb} status=none" \
    > "${temp_file}"

  actual_size="$(stat -c %s "${temp_file}")"
  if [ "${actual_size}" -ne "${expected_size}" ]; then
    echo "Error: chunk ${chunk_index} size mismatch after download (${actual_size} != ${expected_size})."
    rm -f "${temp_file}"
    exit 1
  fi
  mv "${temp_file}" "${part_file}"
}

chunk=0
while [ "${chunk}" -lt "${chunk_count}" ]; do
  download_chunk "${chunk}"
  chunk=$((chunk + 1))
done

echo "Reassembling chunks into ${local_file}..."
temp_local="${local_file}.tmp"
: > "${temp_local}"
chunk=0
while [ "${chunk}" -lt "${chunk_count}" ]; do
  part_file="$(printf "%s/part_%06d.bin" "${parts_dir}" "${chunk}")"
  if [ ! -f "${part_file}" ]; then
    echo "Error: missing chunk file ${part_file}."
    exit 1
  fi
  cat "${part_file}" >> "${temp_local}"
  chunk=$((chunk + 1))
done

assembled_size="$(stat -c %s "${temp_local}")"
if [ "${assembled_size}" -ne "${remote_size}" ]; then
  echo "Error: assembled file size mismatch (${assembled_size} != ${remote_size})."
  rm -f "${temp_local}"
  exit 1
fi

echo "Calculating remote SHA-256..."
remote_sha="$(fly ssh console -a "${APP_NAME}" -C "sha256sum '${REMOTE_PATH}'" | awk '{print $1}' | tail -n1)"
if [ -z "${remote_sha}" ]; then
  echo "Error: failed to compute remote SHA-256."
  rm -f "${temp_local}"
  exit 1
fi
echo "Remote SHA-256: ${remote_sha}"

echo "Calculating local SHA-256..."
local_sha="$(sha256sum "${temp_local}" | awk '{print $1}')"
echo "Local SHA-256:  ${local_sha}"

if [ "${remote_sha}" != "${local_sha}" ]; then
  echo "Error: SHA-256 mismatch; keeping chunk directory for resume and investigation."
  rm -f "${temp_local}"
  exit 1
fi

mv "${temp_local}" "${local_file}"
echo "Download completed and verified: ${local_file}"
if [ "${KEEP_PARTS}" -eq 1 ]; then
  echo "Chunk cache preserved for resume/reverification: ${parts_dir}"
else
  rm -rf "${parts_dir}"
  echo "Removed chunk cache: ${parts_dir}"
fi
