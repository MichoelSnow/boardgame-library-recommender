# Build the frontend separately so the runtime image does not need Node.js.
FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

# Use Python 3.13 slim image
FROM python:3.13-slim

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
RUN pip install --no-cache-dir "poetry==2.3.2" && \
    poetry config virtualenvs.create false && \
    poetry install --without dev --no-root && \
    rm -rf /root/.cache/pip

# Create directory structure
RUN mkdir -p /data
# No need to create images directory since images will be served directly from BoardGameGeek

# Copy backend code
COPY backend/app/ /app/backend/app/
COPY backend/scripts/ /app/backend/scripts/
COPY data_pipeline/ /app/data_pipeline/
# Copy Alembic configuration and migration files for database migrations
COPY backend/alembic/ /app/backend/alembic/
COPY backend/alembic.ini /app/backend/alembic.ini
COPY --from=frontend-builder /app/frontend/build/ /app/frontend/build/
# Create empty __init__.py file for Python package structure
RUN touch /app/backend/__init__.py

RUN cp /app/backend/scripts/start.sh /app/start.sh && \
    chmod +x /app/start.sh /app/backend/scripts/start.sh

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
