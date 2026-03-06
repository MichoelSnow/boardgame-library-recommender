#!/bin/bash
set -euo pipefail

echo "Checking for required database files..."

if [ ! -f /data/boardgames.db ]; then
  echo "Warning: Database file not found in /data/. Creating new SQLite database."
  sqlite3 /data/boardgames.db "VACUUM;"
  chmod 666 /data/boardgames.db
fi

embedding_files=$(ls /data/game_embeddings_*.npz 2>/dev/null | wc -l || true)
mapping_files=$(ls /data/reverse_mappings_*.json 2>/dev/null | wc -l || true)

if [ "${embedding_files}" -eq "0" ] || [ "${mapping_files}" -eq "0" ]; then
  echo "Warning: Recommendation embeddings are missing or incomplete in /data."
  echo "The app will still start, but recommendation endpoints will return empty results until embeddings are restored."
fi

echo "Starting application..."
exec python -m backend.app.runtime_profile --serve
