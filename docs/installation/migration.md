# Machine Migration

This guide covers migrating from legacy Fly apps to new Fly apps.

Scope:
- Postgres data migration
- Runtime artifact migration (`/data/images`, embeddings, reverse mappings)

It assumes fresh deployment was completed with:
- `docs/installation/deployment.md` through step 6.11

## 1. Required Variables

Add the following to your `.env` file:

```
OLD_FLY_DB_APP_NAME_DEV="your-legacy-db-app-name"
OLD_FLY_APP_NAME_DEV="your-legacy-app-name"
OLD_FLY_DB_APP_NAME_PROD="your-legacy-db-app-name"
OLD_FLY_APP_NAME_PROD="your-legacy-app-name"
POSTGRES_USER_OLD="your-legacy-postgres-user"
POSTGRES_DB_OLD="your-legacy-database-name"
POSTGRES_PASSWORD_DEV_OLD="your-legacy-postgres-password"
POSTGRES_PASSWORD_PROD_OLD="your-legacy-postgres-password"
```


Load `.env` file:

```bash
set -a && source .env && set +a
```



## 2. DB Data Migration (Legacy Dev -> New Dev)

Export old dev DB data:

```bash
mkdir -p .tmp
fly ssh console -a "${OLD_FLY_DB_APP_NAME_DEV}" -C "pg_dump \"postgresql://${POSTGRES_USER_OLD}:${POSTGRES_PASSWORD_DEV_OLD}@127.0.0.1:5432/${POSTGRES_DB_OLD}\" --data-only --no-owner --no-privileges" > .tmp/old-dev-data.sql
```

Transform legacy names to current repo schema and remove Alembic row import:

```bash
perl -0777 -pe "s/COPY public\\.pax_games \\(/COPY public.library_games (/g; s/public\\.pax_games_id_seq/public.library_games_id_seq/g; s/^COPY public\\.alembic_version \\(version_num\\) FROM stdin;\\n.*?^\\\\\\.\\n//ms" .tmp/old-dev-data.sql > .tmp/old-dev-data.repo.sql
```

Import into new dev DB:

```bash
cat .tmp/old-dev-data.repo.sql | fly ssh console -a "${FLY_DB_APP_NAME_DEV}" -C "psql \"postgresql://postgres:${POSTGRES_PASSWORD_DEV}@127.0.0.1:5432/${POSTGRES_DB}\" -v ON_ERROR_STOP=1"
cat .tmp/old-dev-data.repo.sql | fly ssh console -a "${FLY_DB_APP_NAME_PROD}" -C "psql \"postgresql://postgres:${POSTGRES_PASSWORD_PROD}@127.0.0.1:5432/${POSTGRES_DB}\" -v ON_ERROR_STOP=1"
```

Verify key row counts:

```bash
fly ssh console -a "${OLD_FLY_DB_APP_NAME_DEV}" -C "psql \"postgresql://${POSTGRES_USER_OLD}:${POSTGRES_PASSWORD_DEV_OLD}@127.0.0.1:5432/${POSTGRES_DB_OLD}\" -c \"SELECT (SELECT COUNT(*) FROM games) AS games, (SELECT COUNT(*) FROM users) AS users, (SELECT COUNT(*) FROM pax_games) AS pax_games;\""
fly ssh console -a "${FLY_DB_APP_NAME_DEV}" -C "psql \"postgresql://postgres:${POSTGRES_PASSWORD_DEV}@127.0.0.1:5432/${POSTGRES_DB}\" -c \"SELECT (SELECT COUNT(*) FROM games) AS games, (SELECT COUNT(*) FROM users) AS users, (SELECT COUNT(*) FROM library_games) AS library_games;\""
fly ssh console -a "${FLY_DB_APP_NAME_PROD}" -C "psql \"postgresql://postgres:${POSTGRES_PASSWORD_PROD}@127.0.0.1:5432/${POSTGRES_DB}\" -c \"SELECT (SELECT COUNT(*) FROM games) AS games, (SELECT COUNT(*) FROM users) AS users, (SELECT COUNT(*) FROM library_games) AS library_games;\""
```

## 3. Runtime Artifact Migration (Old Dev App -> New Dev App)

Create local temp workspace once:

```bash
set -euo pipefail
mkdir -p .tmp
```

Discover image directory layout (set these vars if paths differ):

```bash
fly machine start "$(fly machines list -a "${OLD_FLY_APP_NAME_DEV}" --json | jq -r '.[0].id')" -a "${OLD_FLY_APP_NAME_DEV}" || true
fly ssh console -a "${OLD_FLY_APP_NAME_DEV}" -C "sh -lc 'find /data/images -maxdepth 3 -type d | sort'"
export IMAGE_FULL_DIR="/data/images/games"
export IMAGE_THUMBS_DIR="/data/images/thumbnails"
```

### Embeddings and Mappings

```bash
# Start old dev app machine
fly machine start "$(fly machines list -a "${OLD_FLY_APP_NAME_DEV}" --json | jq -r '.[0].id')" -a "${OLD_FLY_APP_NAME_DEV}" || true

# Local archive (use -z to reduce transfer time/risk window)
fly ssh console -a "${OLD_FLY_APP_NAME_DEV}" -C "sh -lc 'cd /data && tar -czf - game_embeddings_*.npz reverse_mappings_*.json'" > .tmp/dev-embeddings.tgz

# Optional integrity check
tar -tzf .tmp/dev-embeddings.tgz >/dev/null

# Start new dev app machine
fly machine start "$(fly machines list -a "${FLY_APP_NAME_DEV}" --json | jq -r '.[0].id')" -a "${FLY_APP_NAME_DEV}" || true

# Upload archive to new machine
cat .tmp/dev-embeddings.tgz | fly ssh console -a "${FLY_APP_NAME_DEV}" -C "sh -lc 'cat > /data/.import-dev-embeddings.tgz'"

# Extract on new machine
fly ssh console -a "${FLY_APP_NAME_DEV}" -C "sh -lc 'cd /data && tar -xzf /data/.import-dev-embeddings.tgz && rm -f /data/.import-dev-embeddings.tgz'"


# Compare file lists and sizes
fly ssh console -a "${OLD_FLY_APP_NAME_DEV}" -C "sh -lc 'find /data -maxdepth 1 -type f \\( -name \"game_embeddings_*.npz\" -o -name \"reverse_mappings_*.json\" \\) -printf \"%f|%s\n\" | sort'" > .tmp/manifest-old-embeddings.txt
fly ssh console -a "${FLY_APP_NAME_DEV}" -C "sh -lc 'find /data -maxdepth 1 -type f \\( -name \"game_embeddings_*.npz\" -o -name \"reverse_mappings_*.json\" \\) -printf \"%f|%s\n\" | sort'" > .tmp/manifest-new-embeddings.txt
test -s .tmp/manifest-old-embeddings.txt
test -s .tmp/manifest-new-embeddings.txt
diff -u .tmp/manifest-old-embeddings.txt .tmp/manifest-new-embeddings.txt
```


```bash
cat .tmp/dev-embeddings.tgz | fly ssh console -a "${FLY_APP_NAME_PROD}" -C "sh -lc 'cat > /data/.import-dev-embeddings.tgz'"

fly ssh console -a "${FLY_APP_NAME_PROD}" -C "sh -lc 'cd /data && tar -xzf /data/.import-dev-embeddings.tgz && rm -f /data/.import-dev-embeddings.tgz'"

fly ssh console -a "${FLY_APP_NAME_PROD}" -C "sh -lc 'find /data -maxdepth 1 -type f \\( -name \"game_embeddings_*.npz\" -o -name \"reverse_mappings_*.json\" \\) -printf \"%f|%s\n\" | sort'" > .tmp/manifest-prod-embeddings.txt
diff -u .tmp/manifest-old-embeddings.txt .tmp/manifest-prod-embeddings.txt
```

### Images (Full Size) - one-time transfer

```bash
# Start old dev app machine
fly machine start "$(fly machines list -a "${OLD_FLY_APP_NAME_DEV}" --json | jq -r '.[0].id')" -a "${OLD_FLY_APP_NAME_DEV}" || true

# Local archive
fly ssh console -a "${OLD_FLY_APP_NAME_DEV}" -C "sh -lc 'cd / && tar -czf - \"${IMAGE_FULL_DIR#/}\"'" > .tmp/dev-images-full.tgz

# Optional integrity check
tar -tzf .tmp/dev-images-full.tgz >/dev/null

# Start new dev app machine
fly machine start "$(fly machines list -a "${FLY_APP_NAME_DEV}" --json | jq -r '.[0].id')" -a "${FLY_APP_NAME_DEV}" || true

# Upload archive to new machine
cat .tmp/dev-images-full.tgz | fly ssh console -a "${FLY_APP_NAME_DEV}" -C "sh -lc 'cat > /data/.import-dev-images-full.tgz'"

# Extract on new machine
fly ssh console -a "${FLY_APP_NAME_DEV}" -C "sh -lc 'cd / && tar -xzf /data/.import-dev-images-full.tgz && rm -f /data/.import-dev-images-full.tgz'"

# Compare file lists and sizes
fly ssh console -a "${OLD_FLY_APP_NAME_DEV}" -C "sh -lc 'find \"${IMAGE_FULL_DIR}\" -type f -printf \"%P|%s\n\" | sort'" > .tmp/manifest-old-images-full.txt
fly ssh console -a "${FLY_APP_NAME_DEV}" -C "sh -lc 'find \"${IMAGE_FULL_DIR}\" -type f -printf \"%P|%s\n\" | sort'" > .tmp/manifest-new-images-full.txt
test -s .tmp/manifest-old-images-full.txt
test -s .tmp/manifest-new-images-full.txt
diff -u .tmp/manifest-old-images-full.txt .tmp/manifest-new-images-full.txt
```

### Images (Full Size) - resumable file sync (recommended for large sets)

Use this path when image archives are large and volume free space is tight. It
uploads only missing/size-mismatched files and supports resume via state file.

```bash
# If needed, extract the downloaded archive locally first.
# This should produce .tmp/images/data/images/games
mkdir -p .tmp/images
tar -xzf .tmp/dev-images-full.tgz -C .tmp/images

# Sync to Fly app (resumable via state file)
poetry run python scripts/deploy/sync_fly_sftp_files.py \
  --app "${FLY_APP_NAME_DEV}" \
  --local-dir ".tmp/images/data/images/games" \
  --remote-dir "/data/images/games" \
  --state-file ".tmp/sync-images-games-state.json" \
  --batch-size 400
```

Resume after interruption:

```bash
poetry run python scripts/deploy/sync_fly_sftp_files.py \
  --app "${FLY_APP_NAME_DEV}" \
  --local-dir ".tmp/images/data/images/games" \
  --remote-dir "/data/images/games" \
  --state-file ".tmp/sync-images-games-state.json" \
  --batch-size 400
```

Preview uploads without writing:

```bash
poetry run python scripts/deploy/sync_fly_sftp_files.py \
  --app "${FLY_APP_NAME_DEV}" \
  --local-dir ".tmp/images/data/images/games" \
  --remote-dir "/data/images/games" \
  --state-file ".tmp/sync-images-games-state.json" \
  --batch-size 400 \
  --dry-run
```

### Thumbnails

```bash
# Start old dev app machine
fly machine start "$(fly machines list -a "${OLD_FLY_APP_NAME_DEV}" --json | jq -r '.[0].id')" -a "${OLD_FLY_APP_NAME_DEV}" || true

# Local archive
fly ssh console -a "${OLD_FLY_APP_NAME_DEV}" -C "sh -lc 'cd / && tar -czf - \"${IMAGE_THUMBS_DIR#/}\"'" > .tmp/dev-images-thumbs.tgz

# Optional integrity check
tar -tzf .tmp/dev-images-thumbs.tgz >/dev/null

# Start new dev app machine
fly machine start "$(fly machines list -a "${FLY_APP_NAME_DEV}" --json | jq -r '.[0].id')" -a "${FLY_APP_NAME_DEV}" || true

# Upload archive to new machine
cat .tmp/dev-images-thumbs.tgz | fly ssh console -a "${FLY_APP_NAME_DEV}" -C "sh -lc 'cat > /data/.import-dev-images-thumbs.tgz'"

# Extract on new machine
fly ssh console -a "${FLY_APP_NAME_DEV}" -C "sh -lc 'cd / && tar -xzf /data/.import-dev-images-thumbs.tgz && rm -f /data/.import-dev-images-thumbs.tgz'"

# Compare file lists and sizes
fly ssh console -a "${OLD_FLY_APP_NAME_DEV}" -C "sh -lc 'find \"${IMAGE_THUMBS_DIR}\" -type f -printf \"%P|%s\n\" | sort'" > .tmp/manifest-old-images-thumbs.txt
fly ssh console -a "${FLY_APP_NAME_DEV}" -C "sh -lc 'find \"${IMAGE_THUMBS_DIR}\" -type f -printf \"%P|%s\n\" | sort'" > .tmp/manifest-new-images-thumbs.txt
test -s .tmp/manifest-old-images-thumbs.txt
test -s .tmp/manifest-new-images-thumbs.txt
diff -u .tmp/manifest-old-images-thumbs.txt .tmp/manifest-new-images-thumbs.txt
```

```bash
# Upload archive to new machine
cat .tmp/dev-images-thumbs.tgz | fly ssh console -a "${FLY_APP_NAME_PROD}" -C "sh -lc 'cat > /data/.import-dev-images-thumbs.tgz'"

# Extract on new machine
fly ssh console -a "${FLY_APP_NAME_PROD}" -C "sh -lc 'cd / && tar -xzf /data/.import-dev-images-thumbs.tgz && rm -f /data/.import-dev-images-thumbs.tgz'"

# Compare file lists and sizes
fly ssh console -a "${FLY_APP_NAME_PROD}" -C "sh -lc 'find \"${IMAGE_THUMBS_DIR}\" -type f -printf \"%P|%s\n\" | sort'" > .tmp/manifest-prod-images-thumbs.txt
diff -u .tmp/manifest-old-images-thumbs.txt .tmp/manifest-prod-images-thumbs.txt
```


## 4. Dev Functional Validation Gate

Before touching prod, validate dev:

```bash
curl -sS "https://${FLY_APP_NAME_DEV}.fly.dev/api"
fly logs -a "${FLY_APP_NAME_DEV}"
```

Required outcomes:
- Login/auth works
- Library games and images render
- Recommendation endpoints return non-empty results with artifacts present
