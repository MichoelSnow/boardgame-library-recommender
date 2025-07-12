#!/bin/bash

# This script uploads the database and embedding files to the Fly.io volume

# Parse command line arguments
FORCE_OVERWRITE=false
BACKUP_FILES=false
DEBUG=false
LIST_ONLY=false

while getopts "fbdl" opt; do
  case ${opt} in
    f ) FORCE_OVERWRITE=true ;;
    b ) BACKUP_FILES=true ;;
    d ) DEBUG=true ;;
    l ) LIST_ONLY=true ;;
    * ) echo "Usage: $0 [-f] [-b] [-d] [-l]" 
        echo "  -f  Force overwrite of remote files even if they exist with correct size"
        echo "  -b  Backup existing remote files instead of deleting them"
        echo "  -d  Enable debug output"
        echo "  -l  List remote files only (no upload)"
        exit 1 ;;
  esac
done

# Debug function
debug() {
  if [ "$DEBUG" = true ]; then
    # Print to stderr so it doesn't interfere with command substitution
    echo "DEBUG: $1" >&2
  fi
}

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

echo "Found all required files locally. Preparing to check Fly.io volume..."

# Create a temporary container to access the volume
echo "Creating a temporary container to access the volume..."
fly ssh console --command "mkdir -p /data"

# Function to check if a remote file exists
remote_file_exists() {
  local remote_file=$1
  local result=$(fly ssh console --command "ls -la \"$remote_file\" 2>/dev/null || echo 'not_found'" 2>/dev/null)
  
  debug "Remote file check result for $remote_file: '$result'"
  
  if [[ "$result" != *"not_found"* ]] && [[ "$result" != *"No such file"* ]]; then
    debug "File exists: $remote_file"
    return 0  # File exists (success)
  else
    debug "File does not exist: $remote_file"
    return 1  # File doesn't exist (failure)
  fi
}

# Function to get remote file size directly
get_remote_file_size_direct() {
  local remote_file=$1
  local size=$(fly ssh console --command "if [ -f \"$remote_file\" ]; then stat -c%s \"$remote_file\"; else echo '-1'; fi" 2>/dev/null)
  
  # Clean up the output - extract just the number
  size=$(echo "$size" | grep -o '[0-9]\+' | head -1)
  
  if [ -z "$size" ]; then
    debug "Could not determine size using stat for $remote_file, returning -1"
    echo "-1"
  else
    debug "Size from stat for $remote_file: $size"
    echo "$size"
  fi
}

# Function to get remote file size
get_remote_file_size() {
  local remote_file=$1
  
  # Try to get size using stat first (more accurate)
  local size=$(get_remote_file_size_direct "$remote_file")
  
  # If stat failed, try using ls
  if [ "$size" = "-1" ]; then
    debug "Stat failed, trying ls for $remote_file"
    
    # Get the full ls output
    local ls_output=$(fly ssh console --command "ls -la \"$remote_file\" 2>/dev/null" 2>/dev/null)
    debug "ls output: $ls_output"
    
    # Parse the size from the ls output
    # Format: -rw-r--r-- 1 root root 70291379 Jul 10 02:44 /data/file.npz
    #                              ^^^^^^^^ This is the size (5th field)
    size=$(echo "$ls_output" | awk '{print $5}')
    
    debug "Parsed size from ls for $remote_file: $size"
  fi
  
  # Final validation
  if [ -z "$size" ] || ! [[ "$size" =~ ^[0-9]+$ ]]; then
    debug "Invalid size for $remote_file, returning -1"
    echo "-1"
  else
    echo "$size"
  fi
}

# Function to parse human-readable size to bytes
parse_human_size() {
  local size=$1
  
  # Extract the number and unit
  local number=$(echo "$size" | grep -o '[0-9.]\+' | head -1)
  local unit=$(echo "$size" | grep -o '[A-Za-z]\+$')
  
  if [ -z "$number" ]; then
    echo "-1"
    return
  fi
  
  # Convert to bytes based on unit
  case "$unit" in
    K|KB|KiB)
      echo "$(echo "$number * 1024" | bc | cut -d'.' -f1)"
      ;;
    M|MB|MiB)
      echo "$(echo "$number * 1048576" | bc | cut -d'.' -f1)"
      ;;
    G|GB|GiB)
      echo "$(echo "$number * 1073741824" | bc | cut -d'.' -f1)"
      ;;
    *)
      # Assume bytes if no unit
      echo "$number" | cut -d'.' -f1
      ;;
  esac
}

# Function to format file size in human-readable format
format_size() {
  local size=$1
  if [ -z "$size" ] || [ "$size" = "-1" ]; then
    echo "Unknown"
    return
  fi
  
  if command -v numfmt >/dev/null 2>&1; then
    numfmt --to=iec-i --suffix=B --format="%.2f" "$size" 2>/dev/null || echo "$size B"
  else
    # Simple formatting if numfmt is not available
    if [ "$size" -lt 1024 ]; then
      echo "$size B"
    elif [ "$size" -lt 1048576 ]; then
      echo "$(( size / 1024 )) KB"
    elif [ "$size" -lt 1073741824 ]; then
      echo "$(( size / 1048576 )) MB"
    else
      echo "$(( size / 1073741824 )) GB"
    fi
  fi
}

# Function to get remote file last modified time
get_remote_file_modified() {
  local remote_file=$1
  
  # Get the full ls output
  local ls_output=$(fly ssh console --command "ls -la --time-style=long-iso \"$remote_file\" 2>/dev/null" 2>/dev/null)
  
  # Parse the date and time (6th and 7th fields)
  local modified=$(echo "$ls_output" | awk '{print $6, $7}')
  
  if [ -z "$modified" ] || [ "$modified" = " " ]; then
    echo "N/A"
  else
    echo "$modified"
  fi
}

# Function to list a file's information
list_file_info() {
  local local_file=$1
  local remote_file=$2
  local local_size=$(stat -c%s "$local_file")
  local local_modified=$(stat -c%y "$local_file" | cut -d'.' -f1)
  
  printf "%-45s | " "$(basename "$local_file")"
  
  # Format local size
  local_size_human=$(format_size "$local_size")
  
  if remote_file_exists "$remote_file"; then
    remote_size=$(get_remote_file_size "$remote_file")
    remote_modified=$(get_remote_file_modified "$remote_file")
    
    # Format remote size
    remote_size_human=$(format_size "$remote_size")
    
    # Compare sizes
    if [ "$remote_size" -eq "$local_size" ] 2>/dev/null; then
      size_status="✓"
    else
      size_status="✗"
    fi
    
    printf "%-10s | %-10s | %s | %s\n" "$local_size_human" "$remote_size_human" "$size_status" "$remote_modified"
  else
    printf "%-10s | %-10s | %s | %s\n" "$local_size_human" "Not found" "!" "N/A"
  fi
}

# Get list of remote files
get_remote_files() {
  fly ssh console --command "find /data -type f -not -path '*/\\.*' | sort" 2>/dev/null || echo ""
}

# List all files function
list_all_files() {
  echo ""
  echo "Listing files on remote volume:"
  echo "-----------------------------------------------------------------------"
  printf "%-45s | %-10s | %-10s | %s | %s\n" "Filename" "Local" "Remote" "Match" "Remote Modified"
  echo "-----------------------------------------------------------------------"
  
  # List database file
  list_file_info "backend/database/boardgames.db" "/data/boardgames.db"
  
  # List embedding files
  for file in backend/database/game_embeddings_*.npz; do
    remote_file="/data/$(basename "$file")"
    list_file_info "$file" "$remote_file"
  done
  
  for file in backend/database/reverse_mappings_*.json; do
    remote_file="/data/$(basename "$file")"
    list_file_info "$file" "$remote_file"
  done
  
  echo "-----------------------------------------------------------------------"
  echo "Legend: ✓=Sizes match, ✗=Sizes differ, !=File not found on remote"
  echo ""
  
  # Check for other files on the remote that don't exist locally
  echo "Other files found on remote volume:"
  
  # Get list of all remote files
  remote_files=$(get_remote_files)
  
  if [ -z "$remote_files" ]; then
    echo "No additional files found."
    return
  fi
  
  echo "$remote_files" | while read -r remote_file; do
    # Skip if empty line
    if [ -z "$remote_file" ]; then
      continue
    fi
    
    filename=$(basename "$remote_file")
    local_file="backend/database/$filename"
    
    # Skip if this is one of our tracked files
    if [ -f "$local_file" ]; then
      continue
    fi
    
    # Skip directories and special files
    if ! remote_file_exists "$remote_file"; then
      continue
    fi
    
    remote_size=$(get_remote_file_size "$remote_file")
    if [ "$remote_size" = "-1" ]; then
      continue
    fi
    
    remote_size_human=$(format_size "$remote_size")
    remote_modified=$(get_remote_file_modified "$remote_file")
    printf "%-45s | %-10s | %-10s | %s\n" "$filename" "N/A" "$remote_size_human" "$remote_modified"
  done
  echo ""
}

# Function to check if we should upload a file
should_upload() {
  local local_file=$1
  local remote_file=$2
  local local_size=$(stat -c%s "$local_file")
  
  debug "Local file size for $local_file: $local_size"
  
  if [ "$FORCE_OVERWRITE" = true ]; then
    echo "Force overwrite enabled for $remote_file"
    return 0
  fi
  
  if remote_file_exists "$remote_file"; then
    echo "Remote file $remote_file exists"
    
    # Get remote file size
    remote_size=$(get_remote_file_size "$remote_file")
    
    if [ "$remote_size" -lt 1000 ] 2>/dev/null; then
      echo "Remote file $remote_file exists but appears to be a dummy file (size: $remote_size bytes)"
      return 0
    elif [ "$remote_size" != "$local_size" ] 2>/dev/null; then
      echo "Remote file $remote_file exists but has different size (remote: $remote_size, local: $local_size)"
      return 0
    else
      echo "Remote file $remote_file exists with correct size ($remote_size bytes). Skipping upload."
      return 1
    fi
  else
    echo "Remote file $remote_file does not exist"
    return 0
  fi
}

# Function to safely upload a file
safe_upload() {
  local local_file=$1
  local remote_file=$2
  local filename=$(basename "$remote_file")
  local temp_file="/data/.tmp_${filename}"
  local backup_file="/data/.bak_${filename}"
  
  # First upload to a temporary file
  echo "Uploading $local_file to temporary file..."
  fly sftp shell <<EOF
put $local_file $temp_file
EOF

  # Verify the upload was successful
  if ! remote_file_exists "$temp_file"; then
    echo "Error: Failed to upload temporary file $temp_file"
    return 1
  fi
  
  local_size=$(stat -c%s "$local_file")
  temp_size=$(get_remote_file_size "$temp_file")
  
  if [ "$temp_size" != "$local_size" ]; then
    echo "Error: Uploaded file size mismatch (expected: $local_size, got: $temp_size)"
    fly ssh console --command "rm -f \"$temp_file\""
    return 1
  fi
  
  echo "Temporary file uploaded successfully."
  
  # Handle the existing file
  if remote_file_exists "$remote_file"; then
    if [ "$BACKUP_FILES" = true ]; then
      echo "Backing up existing file to $backup_file"
      fly ssh console --command "mv \"$remote_file\" \"$backup_file\""
    else
      echo "Removing existing file $remote_file"
      fly ssh console --command "rm -f \"$remote_file\""
    fi
  fi
  
  # Move the temporary file to the final location
  echo "Moving temporary file to final location..."
  fly ssh console --command "mv \"$temp_file\" \"$remote_file\""
  
  # Verify the final file exists
  if remote_file_exists "$remote_file"; then
    echo "File $remote_file updated successfully."
    return 0
  else
    echo "Error: Failed to move temporary file to final location"
    return 1
  fi
}

# If list-only mode is enabled, just list the files and exit
if [ "$LIST_ONLY" = true ]; then
  list_all_files
  exit 0
fi

# Upload database file
echo "Checking database file..."
if should_upload "backend/database/boardgames.db" "/data/boardgames.db"; then
  safe_upload "backend/database/boardgames.db" "/data/boardgames.db"
fi

# Upload embedding files
echo "Checking embedding files..."
for file in backend/database/game_embeddings_*.npz; do
  remote_file="/data/$(basename "$file")"
  if should_upload "$file" "$remote_file"; then
    safe_upload "$file" "$remote_file"
  fi
done

for file in backend/database/reverse_mappings_*.json; do
  remote_file="/data/$(basename "$file")"
  if should_upload "$file" "$remote_file"; then
    safe_upload "$file" "$remote_file"
  fi
done

echo "Creating images directory on volume if it doesn't exist..."
fly ssh console --command "mkdir -p /data/images"

echo "File upload process completed!"
echo "You can now deploy your application with: fly deploy" 