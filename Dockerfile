# Use Python 3.10 slim image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y gcc curl sqlite3 nodejs npm && rm -rf /var/lib/apt/lists/*

# Copy poetry files
COPY pyproject.toml poetry.lock ./

# Install poetry and dependencies
RUN pip install poetry && poetry config virtualenvs.create false && poetry install --without dev --no-root

# Create directory structure
RUN mkdir -p /data
# No need to create images directory since images will be served directly from BoardGameGeek

# Copy frontend code and build it
COPY frontend/ /app/frontend/
WORKDIR /app/frontend
RUN npm ci
RUN npm run build
WORKDIR /app

# Copy backend code
COPY backend/app/ /app/backend/app/
# Copy Alembic configuration and migration files for database migrations
COPY backend/alembic/ /app/backend/alembic/
COPY backend/alembic.ini /app/backend/alembic.ini
# Create empty __init__.py file for Python package structure
RUN touch /app/backend/__init__.py

# Create start.sh script
COPY <<EOF /app/start.sh
#!/bin/bash
echo "Checking for required database files..."

# Create required directories
# No need to create images directory

# Check for database file
if [ ! -f /data/boardgames.db ]; then
  echo "Warning: Database file not found in /data/. Creating new SQLite database."
  # Create a properly initialized SQLite database
  sqlite3 /data/boardgames.db "VACUUM;"
  chmod 666 /data/boardgames.db
fi

# Check for embedding files
EMBEDDING_FILES=\$(ls /data/game_embeddings_*.npz 2>/dev/null | wc -l)
MAPPING_FILES=\$(ls /data/reverse_mappings_*.json 2>/dev/null | wc -l)

if [ "\$EMBEDDING_FILES" -eq "0" ] || [ "\$MAPPING_FILES" -eq "0" ]; then
  echo "Warning: Embedding files not found in /data/. Creating dummy files."
  
  # Generate a timestamp for consistent naming
  TIMESTAMP=\$(date +%s)
  
  # Create dummy embedding files if they don't exist
  if [ "\$EMBEDDING_FILES" -eq "0" ]; then
    # Create a Python script to generate a valid sparse matrix file
    cat > /tmp/create_sparse.py << 'PYEOF'
import numpy as np
from scipy import sparse
import os
import sys

try:
    # Create a small but valid sparse matrix (10x10 with some random values)
    # This mimics a real embedding matrix better than 1x1
    np.random.seed(42)  # For reproducible results
    
    # Create a sparse matrix with some non-zero values
    data = np.random.rand(20) * 0.1  # Small random values
    row = np.random.randint(0, 10, 20)
    col = np.random.randint(0, 10, 20)
    matrix = sparse.csr_matrix((data, (row, col)), shape=(10, 10))
    
    # Normalize the matrix (common in embedding matrices)
    matrix = matrix.astype(np.float32)
    
    # Save it to the dummy file with timestamp
    output_file = f"/data/game_embeddings_{sys.argv[1]}.npz"
    sparse.save_npz(output_file, matrix)
    
    # Verify the file was created correctly
    print(f"Created sparse matrix file at {output_file}")
    print(f"File size: {os.path.getsize(output_file)} bytes")
    
    # Test loading the file to ensure it's valid
    test_matrix = sparse.load_npz(output_file)
    print(f"Matrix shape: {test_matrix.shape}")
    print(f"Matrix type: {type(test_matrix)}")
    print("✓ Sparse matrix file created successfully and verified")
    
except Exception as e:
    print(f"Error creating sparse matrix: {e}")
    sys.exit(1)
PYEOF
    python /tmp/create_sparse.py "\$TIMESTAMP"
    # Verify the file exists and has content
    if [ ! -s "/data/game_embeddings_\${TIMESTAMP}.npz" ]; then
      echo "Error: Failed to create valid sparse matrix file"
      exit 1
    fi
  fi
  if [ "\$MAPPING_FILES" -eq "0" ]; then
    # Create a valid mapping file with multiple entries
    cat > /tmp/create_mapping.py << 'PYEOF'
import json
import os
import sys

try:
    # Create a mapping that matches the sparse matrix dimensions
    # Map indices 0-9 to game IDs 1-10
    mapping = {str(i): i+1 for i in range(10)}
    
    # Save to file with timestamp
    output_file = f"/data/reverse_mappings_{sys.argv[1]}.json"
    with open(output_file, "w") as f:
        json.dump(mapping, f, indent=2)
    
    # Verify the file was created correctly
    print(f"Created mapping file at {output_file}")
    print(f"File size: {os.path.getsize(output_file)} bytes")
    
    # Test loading the file to ensure it's valid JSON
    with open(output_file, "r") as f:
        test_mapping = json.load(f)
    print(f"Mapping entries: {len(test_mapping)}")
    print(f"Sample mapping: {dict(list(test_mapping.items())[:3])}")
    print("✓ Mapping file created successfully and verified")
    
except Exception as e:
    print(f"Error creating mapping file: {e}")
    sys.exit(1)
PYEOF
    python /tmp/create_mapping.py "\$TIMESTAMP"
    # Verify the file exists and has content
    if [ ! -s "/data/reverse_mappings_\${TIMESTAMP}.json" ]; then
      echo "Error: Failed to create valid mapping file"
      exit 1
    fi
  fi
fi

echo "Starting application..."

# Start the application
exec uvicorn backend.app.main:app --host 0.0.0.0 --port 8080
EOF

RUN chmod +x /app/start.sh

# Set environment variables
ENV PYTHONPATH=/app
ENV DATABASE_DIR=/data
ENV DATABASE_PATH=/data/boardgames.db
# No need to set IMAGES_DIR since images will be served from BoardGameGeek
ENV NODE_ENV=production

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/ || exit 1

# Run the application
CMD ["/app/start.sh"] 