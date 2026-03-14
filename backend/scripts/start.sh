#!/bin/bash
set -euo pipefail

echo "Checking for required database files..."

if [ -z "${DATABASE_URL:-}" ]; then
  echo "Error: DATABASE_URL is required for Fly deployments."
  exit 1
fi

embedding_files=$(ls /data/game_embeddings_*.npz 2>/dev/null | wc -l || true)
mapping_files=$(ls /data/reverse_mappings_*.json 2>/dev/null | wc -l || true)

if [ "${embedding_files}" -eq "0" ] || [ "${mapping_files}" -eq "0" ]; then
  echo "Warning: Recommendation embeddings are missing or incomplete in /data."
  echo "The app will still start, but recommendation endpoints will return empty results until embeddings are restored."
fi

echo "Starting application..."
exec python -m backend.app.runtime_profile --serve
