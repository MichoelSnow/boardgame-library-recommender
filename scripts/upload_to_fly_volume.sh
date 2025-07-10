#!/bin/bash

# This script uploads the database and embedding files to the Fly.io volume

# Check if the files exist locally
if [ ! -f "backend/database/boardgames.db" ]; then
  echo "Error: Database file not found at backend/database/boardgames.db"
  exit 1
fi

# Check for embedding files
EMBEDDING_FILES=$(ls backend/database/game_embeddings_*.npz 2>/dev/null | wc -l)
MAPPING_FILES=$(ls backend/database/reverse_mappings_*.json 2>/dev/null | wc -l)

if [ "$EMBEDDING_FILES" -eq "0" ] || [ "$MAPPING_FILES" -eq "0" ]; then
  echo "Error: Embedding files not found in backend/database/"
  exit 1
fi

echo "Found all required files locally. Uploading to Fly.io volume..."

# Create a temporary container to upload files
echo "Creating a temporary container to access the volume..."
fly ssh console --command "mkdir -p /data"

# Upload database file
echo "Uploading database file..."
fly sftp shell <<EOF
put backend/database/boardgames.db /data/boardgames.db
EOF

# Upload embedding files
echo "Uploading embedding files..."
for file in backend/database/game_embeddings_*.npz; do
  fly sftp shell <<EOF
put "$file" /data/$(basename "$file")
EOF
done

for file in backend/database/reverse_mappings_*.json; do
  fly sftp shell <<EOF
put "$file" /data/$(basename "$file")
EOF
done

echo "Creating images directory on volume..."
fly ssh console --command "mkdir -p /data/images"

echo "All files uploaded successfully!"
echo "You can now deploy your application with: fly deploy" 