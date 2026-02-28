# Build the frontend separately so the runtime image does not need Node.js.
FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

# Use Python 3.10 slim image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Build metadata
ARG GIT_SHA=unknown
ARG BUILD_TIMESTAMP=unknown

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends gcc curl sqlite3 && rm -rf /var/lib/apt/lists/*

# Copy poetry files
COPY pyproject.toml poetry.lock ./

# Install poetry and dependencies
RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --without dev --no-root && \
    rm -rf /root/.cache/pip

# Create directory structure
RUN mkdir -p /data
# No need to create images directory since images will be served directly from BoardGameGeek

# Copy backend code
COPY backend/app/ /app/backend/app/
# Copy Alembic configuration and migration files for database migrations
COPY backend/alembic/ /app/backend/alembic/
COPY backend/alembic.ini /app/backend/alembic.ini
COPY --from=frontend-builder /app/frontend/build/ /app/frontend/build/
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
  echo "Warning: Recommendation embeddings are missing or incomplete in /data."
  echo "The app will still start, but recommendation endpoints will return empty results until embeddings are restored."
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
ENV APP_GIT_SHA=${GIT_SHA}
ENV APP_BUILD_TIMESTAMP=${BUILD_TIMESTAMP}
# No need to set IMAGES_DIR since images will be served from BoardGameGeek
ENV NODE_ENV=production

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/ || exit 1

# Run the application
CMD ["/app/start.sh"] 
