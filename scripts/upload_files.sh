#!/bin/bash

# This script uploads a single file to the Fly.io volume

if [ $# -ne 2 ]; then
  echo "Usage: $0 <local_file> <remote_path>"
  exit 1
fi

LOCAL_FILE=$1
REMOTE_PATH=$2

echo "Uploading $LOCAL_FILE to $REMOTE_PATH..."
fly ssh sftp put "$LOCAL_FILE" "$REMOTE_PATH"

echo "Upload complete!" 