# Data Pipeline

## Scope
- BoardGameGeek ingest pipeline, normalization, feature generation, and asset preparation.
- Exploratory notebooks for analysis/prototyping only.

## Directory Layout
- `src/ingest/`
  - `get_ranks.py`
  - `get_game_data.py`
  - `get_ratings.py`
- `src/transform/`
  - `data_processor.py`
- `src/features/`
  - `create_embeddings.py`
  - `create_content_embeddings.py`
  - `recommender.py`
- `src/assets/`
  - `sync_fly_images.py`
  - `download_images.py`
- `src/common/`
  - `logging_utils.py`
- `notebooks/`
  - exploratory analysis and one-off investigations
- `tests/`
  - pipeline-focused tests

## Quick Start
| Scenario | Steps |
| --- | --- |
| First remote ingest run | Create app/volume -> set `.env` -> `fly_ingest_set_secrets.sh` -> `fly_ingest_deploy.sh` -> `fly_ingest_start.sh` |
| Resume remote ingest after failure | `fly_ingest_status.sh` -> check logs -> `fly_ingest_start.sh` |
| Download remote artifacts after run | Enable maintenance mode -> start machine -> `fly_ingest_list_artifacts.sh` -> `fly_ingest_download_artifact.sh` -> disable maintenance mode -> stop machine |
| Local processing + import | Process (`data_processor`) -> build collaborative embeddings (`create_embeddings`) -> build content embeddings (`create_content_embeddings`) -> run Alembic -> import data/library |

## Data Collection

Use these commands from repo root.

### Local collection (run on your machine)

1. Collect rankings:
```bash
poetry run python -m data_pipeline.src.ingest.get_ranks
```

Required input:
- `--ranks-zip-url "<signed-url>"` or `BGG_RANKS_ZIP_URL`.
- To obtain the signed URL:
  1. log in to BoardGameGeek
  2. open `https://boardgamegeek.com/data_dumps/bg_ranks`
  3. copy the current boardgame ranks ZIP link

2. Collect game metadata:
```bash
poetry run python -m data_pipeline.src.ingest.get_game_data
poetry run python -m data_pipeline.src.ingest.get_game_data --continue-from-last
```

3. Collect ratings:
```bash
poetry run python -m data_pipeline.src.ingest.get_ratings
poetry run python -m data_pipeline.src.ingest.get_ratings --continue-from-last
```

Token requirements:
- `BGG_TOKEN` is required for `get_game_data` and `get_ratings`.
- Auth format: `Authorization: Bearer <token>`.
- Scripts check process env first, then repo-root `.env`.

Outputs:
- Rankings: `data/ingest/ranks/boardgame_ranks_*.csv`
- Game data: `data/ingest/game_data/boardgame_data_*.duckdb`
- Ratings: `data/ingest/ratings/boardgame_ratings_*.duckdb`

Ratings DuckDB details:
- Table: `boardgame_ratings(game_id BIGINT, rating_round DOUBLE, username TEXT)`
- Index: `idx_boardgame_ratings` on `(game_id, rating_round, username)`
- Inserts are de-duplicated and resume-safe.

### Remote collection on Fly (`bg-lib-ingest`)

Use dedicated ingest app/machine, not request-serving app machines.

Key files:
- Fly config: `fly.ingest.toml`
- Image build: `Dockerfile.ingest`
- Orchestrator: `scripts/data_pipeline/run_ingest_pipeline.py`
- Deploy/start/status helpers:
  - `scripts/deploy/fly_ingest_deploy.sh`
  - `scripts/deploy/fly_ingest_start.sh`
  - `scripts/deploy/fly_ingest_status.sh`
  - `scripts/deploy/fly_ingest_set_secrets.sh`

Required `.env` values for remote ingest:
```bash
FLY_APP_NAME_INGEST=bg-lib-ingest
BGG_TOKEN=<your_bgg_token>
BGG_RANKS_ZIP_URL=<signed_bgg_ranks_zip_url>
INGEST_NOTIFY_EMAIL_TO=<your_email>
INGEST_NOTIFY_EMAIL_FROM=<verified_sender>
BREVO_SMTP_LOGIN=<brevo_smtp_login_or_username>
BREVO_SMTP_KEY=<brevo_smtp_key>
# optional overrides:
# INGEST_NOTIFY_SMTP_HOST=smtp-relay.brevo.com
# INGEST_NOTIFY_SMTP_PORT=587
# INGEST_NOTIFY_SMTP_STARTTLS=true
```

One-time bootstrap:
```bash
fly apps create "${FLY_APP_NAME_INGEST:-bg-lib-ingest}"
fly volumes create bg_lib_ingest_data \
  --app "${FLY_APP_NAME_INGEST:-bg-lib-ingest}" \
  --region iad \
  --size 4 \
  --yes
```

Regular remote run flow:
1. Deploy image:
```bash
scripts/deploy/fly_ingest_deploy.sh
```
2. Sync secrets from `.env`:
```bash
scripts/deploy/fly_ingest_set_secrets.sh
```
3. Start ingest:
```bash
scripts/deploy/fly_ingest_start.sh
```
4. Check status:
```bash
scripts/deploy/fly_ingest_status.sh
```
5. Optional logs:
```bash
fly logs -a "${FLY_APP_NAME_INGEST:-bg-lib-ingest}"
fly ssh console -a "${FLY_APP_NAME_INGEST:-bg-lib-ingest}" -C "cat /app/data/ingest/run_state.json"
```

Remote run behavior:
- Stage order: `get_ranks -> get_game_data -> get_ratings`
- `get_game_data` and `get_ratings` run with `--continue-from-last`
- On repeated stage failure:
  - alert is sent (if configured)
  - stage attempts are reset to `0`
  - run exits cleanly (future runs are not blocked)
- On completion, completion alert is sent (if configured)
- Machine exits when pipeline exits (restart policy `no`)
- Orchestrator/stage logs are written under `/app/data/logs/ingest/*`

Maintenance mode (manual SSH/debug mode):
1. Enable:
```bash
fly secrets set INGEST_MAINTENANCE_MODE=true -a "${FLY_APP_NAME_INGEST:-bg-lib-ingest}"
```
2. Start machine:
```bash
scripts/deploy/fly_ingest_start.sh
```
3. SSH and run manual commands:
```bash
fly ssh console -a "${FLY_APP_NAME_INGEST:-bg-lib-ingest}"
```
4. Stop machine when finished:
```bash
fly machine list -a "${FLY_APP_NAME_INGEST:-bg-lib-ingest}"
fly machine stop <MACHINE_ID> -a "${FLY_APP_NAME_INGEST:-bg-lib-ingest}"
```
5. Disable maintenance mode before normal runs:
```bash
fly secrets set INGEST_MAINTENANCE_MODE=false -a "${FLY_APP_NAME_INGEST:-bg-lib-ingest}"
# or remove the override entirely:
fly secrets unset INGEST_MAINTENANCE_MODE -a "${FLY_APP_NAME_INGEST:-bg-lib-ingest}"
```

### Export ingest artifacts from Fly to local

This handoff is part of collection and must happen before local processing.

If the pipeline has already finished (machine stopped), you must use maintenance mode to keep the machine up long enough to list/download files.

Enable maintenance mode and start machine:
```bash
fly secrets set INGEST_MAINTENANCE_MODE=true -a "${FLY_APP_NAME_INGEST:-bg-lib-ingest}"
scripts/deploy/fly_ingest_start.sh
```

List remote files:
```bash
scripts/deploy/fly_ingest_list_artifacts.sh
```

Download (resumable + checksum verified):
```bash
# ranks -> data/ingest/ranks
scripts/deploy/fly_ingest_download_artifact.sh \
  --remote-path /app/data/ingest/ranks/boardgame_ranks_<date>.csv

# game_data -> data/ingest/game_data
scripts/deploy/fly_ingest_download_artifact.sh \
  --remote-path /app/data/ingest/game_data/boardgame_data_<timestamp>.duckdb \
  --chunk-mb 256

# ratings -> data/ingest/ratings
scripts/deploy/fly_ingest_download_artifact.sh \
  --remote-path /app/data/ingest/ratings/boardgame_ratings_<timestamp>.duckdb \
  --chunk-mb 256
```

Disable maintenance mode when done:
```bash
fly secrets set INGEST_MAINTENANCE_MODE=false -a "${FLY_APP_NAME_INGEST:-bg-lib-ingest}"
# or remove the override entirely:
fly secrets unset INGEST_MAINTENANCE_MODE -a "${FLY_APP_NAME_INGEST:-bg-lib-ingest}"
```

Stop machine when done:
```bash
fly machine stop "$(fly machine list -a "${FLY_APP_NAME_INGEST:-bg-lib-ingest}" --json | jq -r '.[0].id')" -a "${FLY_APP_NAME_INGEST:-bg-lib-ingest}"
```

```bash
fly machine list -a "${FLY_APP_NAME_INGEST:-bg-lib-ingest}"
fly machine stop <MACHINE_ID> -a "${FLY_APP_NAME_INGEST:-bg-lib-ingest}"
```



Download notes:
- Default output dir is inferred from remote path
- Download resumes from existing chunk cache
- Final file is promoted only after SHA-256 match
- `.parts` cache is removed on success (use `--keep-parts` to retain)

## Data Processing

### Process and normalize relational outputs
```bash
poetry run python -m data_pipeline.src.transform.data_processor
```

Behavior:
- Merges ranking + detailed game data
- Normalizes relationship tables
- Writes timestamped outputs under `data/transform/processed/<timestamp>/`

### Generate collaborative filtering artifacts
```bash
poetry run python -m data_pipeline.src.features.create_embeddings
```

Behavior:
- Builds sparse recommendation artifacts from ratings data
- Writes embedding/mapping outputs used by backend recommender runtime

### Generate content-based artifacts
```bash
poetry run python -m data_pipeline.src.features.create_content_embeddings
```

Behavior:
- Builds content feature embeddings from processed game properties.
- Factors include:
  - strong: mechanics, categories, families, designers, artists
  - medium: suggested players, average-weight bucket, playtime bucket
  - light: publisher
- Writes timestamped content artifacts under `backend/database/`:
  - `content_embeddings_<timestamp>.npz`
  - `content_reverse_mappings_<timestamp>.json`
  - `content_feature_mappings_<timestamp>.json`
  - `content_embeddings_metadata_<timestamp>.json`

## Data Import/Export

### Local import (SQLite or Postgres)

1. Run Alembic migrations:
```bash
# from repo root
poetry run alembic -c backend/alembic.ini upgrade head
```

2. Import processed game data:
```bash
poetry run python backend/app/import_data.py
```

3. Optional reset import:
```bash
poetry run python backend/app/import_data.py --delete-existing
```

4. Library convention import:
```bash
poetry run python backend/app/import_library_data.py --csv data/library/bg_lib_games_<timestamp>.csv
poetry run python backend/app/import_library_data.py --csv data/library/bg_lib_games_<timestamp>.csv --delete-existing
```

Notes:
- Local DB target is controlled by your local `DATABASE_URL` (SQLite fallback or Postgres).
- `import_data.py` imports latest `processed_games_*` timestamp set.
- `import_library_data.py` imports legacy `data/library/bg_lib_games_*.csv` into
  `library_imports` + `library_import_items` (not `library_games`).

### Remote import (Fly app, Postgres only; both `dev` and `prod`)

Run inside the target app container so app + DB configuration match deploy environment.

Recommended execution order for remote import:
1. Stage processed data + embeddings on remote machine (section below).
2. Backup the target remote database.
3. Run clean reset import (`--delete-existing`).
4. (Optional) import library convention data.

#### Stage processed data + embeddings on remote app machine (required before import)

Set target app (`dev` or `prod`) and identify latest local artifacts:
```bash
# choose target app
TARGET_APP="${FLY_APP_NAME_DEV}"    # or "${FLY_APP_NAME_PROD}"

# latest processed timestamp directory
PROCESSED_TS="$(find data/transform/processed -mindepth 1 -maxdepth 1 -type d -printf "%f\n" | rg '^[0-9]+$' | sort -n | tail -1)"

# latest embeddings timestamp (must have both files)
EMBED_TS="$(find backend/database -maxdepth 1 -type f -name 'game_embeddings_*.npz' -printf "%f\n" | sed -E 's/^game_embeddings_([0-9]+)\.npz$/\1/' | sort -n | tail -1)"

# latest content embeddings timestamp (must have both files)
CONTENT_EMBED_TS="$(find backend/database -maxdepth 1 -type f -name 'content_embeddings_*.npz' -printf "%f\n" | sed -E 's/^content_embeddings_([0-9]+)\.npz$/\1/' | sort -n | tail -1)"

echo "TARGET_APP=${TARGET_APP}"
echo "PROCESSED_TS=${PROCESSED_TS}"
echo "EMBED_TS=${EMBED_TS}"
echo "CONTENT_EMBED_TS=${CONTENT_EMBED_TS}"
```

Generate local checksum manifests:
```bash
mkdir -p .tmp/transfer_manifests

(
  cd "data/transform/processed/${PROCESSED_TS}" && \
  sha256sum processed_games_*_"${PROCESSED_TS}".csv | sort
) > ".tmp/transfer_manifests/processed_${PROCESSED_TS}.sha256"

(
  cd backend/database && \
  sha256sum \
    "game_embeddings_${EMBED_TS}.npz" \
    "reverse_mappings_${EMBED_TS}.json" | sort
) > ".tmp/transfer_manifests/embeddings_${EMBED_TS}.sha256"

(
  cd backend/database && \
  sha256sum \
    "content_embeddings_${CONTENT_EMBED_TS}.npz" \
    "content_reverse_mappings_${CONTENT_EMBED_TS}.json" \
    "content_feature_mappings_${CONTENT_EMBED_TS}.json" \
    "content_embeddings_metadata_${CONTENT_EMBED_TS}.json" | sort
) > ".tmp/transfer_manifests/content_embeddings_${CONTENT_EMBED_TS}.sha256"
```

Copy processed CSV set to remote app:
```bash
tar -C data/transform/processed -czf - "${PROCESSED_TS}" | \
fly ssh console -a "${TARGET_APP}" -C \
  "sh -lc 'mkdir -p /data/transform/processed && tar -xzf - -C /data/transform/processed'"
```

Copy embeddings + reverse mappings to remote `/data`:
```bash
cat "backend/database/game_embeddings_${EMBED_TS}.npz" | \
  fly ssh console -a "${TARGET_APP}" -C \
  "sh -lc 'cat > /data/game_embeddings_${EMBED_TS}.npz'"

cat "backend/database/reverse_mappings_${EMBED_TS}.json" | \
  fly ssh console -a "${TARGET_APP}" -C \
  "sh -lc 'cat > /data/reverse_mappings_${EMBED_TS}.json'"
```

Copy content embeddings + mappings to remote `/data`:
```bash
cat "backend/database/content_embeddings_${CONTENT_EMBED_TS}.npz" | \
  fly ssh console -a "${TARGET_APP}" -C \
  "sh -lc 'cat > /data/content_embeddings_${CONTENT_EMBED_TS}.npz'"

cat "backend/database/content_reverse_mappings_${CONTENT_EMBED_TS}.json" | \
  fly ssh console -a "${TARGET_APP}" -C \
  "sh -lc 'cat > /data/content_reverse_mappings_${CONTENT_EMBED_TS}.json'"

cat "backend/database/content_feature_mappings_${CONTENT_EMBED_TS}.json" | \
  fly ssh console -a "${TARGET_APP}" -C \
  "sh -lc 'cat > /data/content_feature_mappings_${CONTENT_EMBED_TS}.json'"

cat "backend/database/content_embeddings_metadata_${CONTENT_EMBED_TS}.json" | \
  fly ssh console -a "${TARGET_APP}" -C \
  "sh -lc 'cat > /data/content_embeddings_metadata_${CONTENT_EMBED_TS}.json'"
```

Verify remote checksums match local manifests:
```bash
fly ssh console -a "${TARGET_APP}" -C \
  "sh -lc 'cd /data/transform/processed/${PROCESSED_TS} && sha256sum processed_games_*_${PROCESSED_TS}.csv | sort'" \
  > ".tmp/transfer_manifests/remote_processed_${PROCESSED_TS}.sha256"

diff -u \
  ".tmp/transfer_manifests/processed_${PROCESSED_TS}.sha256" \
  ".tmp/transfer_manifests/remote_processed_${PROCESSED_TS}.sha256"

fly ssh console -a "${TARGET_APP}" -C \
  "sh -lc 'cd /data && sha256sum game_embeddings_${EMBED_TS}.npz reverse_mappings_${EMBED_TS}.json | sort'" \
  > ".tmp/transfer_manifests/remote_embeddings_${EMBED_TS}.sha256"

diff -u \
  ".tmp/transfer_manifests/embeddings_${EMBED_TS}.sha256" \
  ".tmp/transfer_manifests/remote_embeddings_${EMBED_TS}.sha256"

fly ssh console -a "${TARGET_APP}" -C \
  "sh -lc 'cd /data && sha256sum content_embeddings_${CONTENT_EMBED_TS}.npz content_reverse_mappings_${CONTENT_EMBED_TS}.json content_feature_mappings_${CONTENT_EMBED_TS}.json content_embeddings_metadata_${CONTENT_EMBED_TS}.json | sort'" \
  > ".tmp/transfer_manifests/remote_content_embeddings_${CONTENT_EMBED_TS}.sha256"

diff -u \
  ".tmp/transfer_manifests/content_embeddings_${CONTENT_EMBED_TS}.sha256" \
  ".tmp/transfer_manifests/remote_content_embeddings_${CONTENT_EMBED_TS}.sha256"
```

If `diff` returns no output, transfer verification passed.

Runtime note:
- Collaborative mode needs `game_embeddings_*` + `reverse_mappings_*`.
- Hybrid mode content rerank needs `content_embeddings_*` + `content_reverse_mappings_*`.
- `content_feature_mappings_*` and `content_embeddings_metadata_*` are not required at request time, but should be transferred for reproducibility/debugging.

#### Backup remote DB before reset/import

From repo root (local machine):
```bash
# dev backup
poetry run python scripts/db/fly_postgres_backup.py \
  --env dev \
  --output ".tmp/dev-before-import-$(date -u +%Y%m%dT%H%M%SZ).sql"

# prod backup
poetry run python scripts/db/fly_postgres_backup.py \
  --env prod \
  --output ".tmp/prod-before-import-$(date -u +%Y%m%dT%H%M%SZ).sql"
```

Notes:
- `scripts/db/fly_postgres_backup.py` auto-loads repo-root `.env` for `POSTGRES_USER` and `POSTGRES_DB` defaults.
- CLI flags still override defaults when needed:
```bash
poetry run python scripts/db/fly_postgres_backup.py \
  --env dev \
  --postgres-user postgres \
  --postgres-db boardgame_recommender \
  --output ".tmp/dev-before-import-$(date -u +%Y%m%dT%H%M%SZ).sql"
```

Optional faster mode (write backup on remote DB machine instead of streaming locally):
```bash
# set this once for the current run
BACKUP_ENV=dev

if [ "${BACKUP_ENV}" = "dev" ]; then
  DB_APP="${FLY_DB_APP_NAME_DEV}"
  BACKUP_PREFIX="dev-before-import"
else
  DB_APP="${FLY_DB_APP_NAME_PROD}"
  BACKUP_PREFIX="prod-before-import"
fi

BACKUP_REMOTE_PATH="/var/lib/postgresql/backups/${BACKUP_PREFIX}-$(date -u +%Y%m%dT%H%M%SZ).sql"

poetry run python scripts/db/fly_postgres_backup.py \
  --env "${BACKUP_ENV}" \
  --remote-output "${BACKUP_REMOTE_PATH}"
```

Check remote backup file size (exact file path, no guessing):
```bash
fly ssh console -a "${DB_APP}" -C \
  "sh -lc 'test -s \"${BACKUP_REMOTE_PATH}\" && ls -lh \"${BACKUP_REMOTE_PATH}\" && du -h \"${BACKUP_REMOTE_PATH}\" | cut -f1 | sed \"s/^/size_human=/\"'"
```

Restore validation from that same remote backup file (into disposable restore DB on remote machine):
```bash
poetry run python scripts/db/fly_postgres_restore.py \
  --env "${BACKUP_ENV}" \
  --remote-input "${BACKUP_REMOTE_PATH}" \
  --restore-db bg_lib_recommender_restore_test
```

Delete remote backup file after successful migration:
```bash
fly ssh console -a "${DB_APP}" -C \
  "sh -lc 'rm -f \"${BACKUP_REMOTE_PATH}\"'"
```

Or combine restore+delete in one command:
```bash
poetry run python scripts/db/fly_postgres_restore.py \
  --env "${BACKUP_ENV}" \
  --remote-input "${BACKUP_REMOTE_PATH}" \
  --restore-db bg_lib_recommender_restore_test \
  --delete-remote-after-restore
```

If you lose `BACKUP_REMOTE_PATH`, recover the latest remote file for the current env:
```bash
BACKUP_REMOTE_PATH="$(fly ssh console -a "${DB_APP}" -C "sh -lc 'ls -1t /var/lib/postgresql/backups/${BACKUP_PREFIX}-*.sql 2>/dev/null | head -n1'" | tail -n1)"
```

#### Clean reset + import (remote app)

Recommended (detached remote job; resilient to SSH disconnects):
```bash
scripts/deploy/fly_import_data_job.sh dev start
scripts/deploy/fly_import_data_job.sh dev status
scripts/deploy/fly_import_data_job.sh dev tail
scripts/deploy/fly_import_data_job.sh dev log
```

```bash
scripts/deploy/fly_import_data_job.sh prod start
scripts/deploy/fly_import_data_job.sh prod status
scripts/deploy/fly_import_data_job.sh prod tail
scripts/deploy/fly_import_data_job.sh prod log
```

`log` downloads the latest remote import log to local:
- `logs/import_data/<app_name>_import_data_latest_<timestamp>.log`

Postgres import behavior note:
- `data_pipeline/src/transform/data_processor.py` computes `avg_box_volume` during transform from English version dimensions.
- `app/import_data.py` imports `avg_box_volume` directly from `processed_games_data_*`.

Optional controls:
```bash
scripts/deploy/fly_import_data_job.sh dev stop
scripts/deploy/fly_import_data_job.sh prod stop
```

Notes:
- `start` captures the prior autostop mode, sets `autostop=off`, and starts a local watcher that auto-restores the prior mode after import completion.
- `status` is read-only and does not modify machine settings; it prints machine service policy (`autostop`/`autostart`) and local watcher status.
- `stop` is an explicit fallback that force-restores machine `autostop=stop`.
- Keep the local terminal host running while the detached import is active so the watcher can complete the auto-restore.

Fallback foreground SSH command:
```bash
# dev
fly ssh console -a "${FLY_APP_NAME_DEV}" -C \
  'sh -lc "cd /app/backend && poetry run alembic -c alembic.ini upgrade head && poetry run python app/import_data.py --delete-existing"'
```

```bash
# prod
fly ssh console -a "${FLY_APP_NAME_PROD}" -C \
  'sh -lc "cd /app/backend && poetry run alembic -c alembic.ini upgrade head && poetry run python app/import_data.py --delete-existing"'
```

Library convention data import in remote app (into `library_imports` + `library_import_items`):
```bash
# dev
fly ssh console -a "${FLY_APP_NAME_DEV}" -C \
  'sh -lc "cd /app/backend && poetry run python app/import_library_data.py --csv /data/library/bg_lib_games_<timestamp>.csv"'

# prod
fly ssh console -a "${FLY_APP_NAME_PROD}" -C \
  'sh -lc "cd /app/backend && poetry run python app/import_library_data.py --csv /data/library/bg_lib_games_<timestamp>.csv"'
```

## Errata

### Image seeding to Fly volumes

Active runtime for `dev` and `prod` is Fly-local images:
- `IMAGE_BACKEND=fly_local`
- `IMAGE_STORAGE_DIR=/data/images`

Primary seed command (BGG origin -> Fly/local image storage):

```bash
poetry run python -m data_pipeline.src.assets.sync_fly_images --scope all-qualified --max-rank 10000
```

Scope variants:

```bash
poetry run python -m data_pipeline.src.assets.sync_fly_images --scope library-only
poetry run python -m data_pipeline.src.assets.sync_fly_images --scope top-rank-only --max-rank 10000
```

Dry-run:

```bash
poetry run python -m data_pipeline.src.assets.sync_fly_images --scope all-qualified --max-rank 10000 --dry-run
```

For Fly machine commands (dev/prod `fly ssh` usage), file counts, and validation:
- [docs/core/convention_ops.md](../docs/core/convention_ops.md)

Import integration commands:

```bash
poetry run python backend/app/import_data.py --sync-images --sync-images-max-rank 10000
```

### Notebook policy
- Notebooks are allowed only under `data_pipeline/notebooks/`.
- No secrets/credentials/tokens in notebook source or outputs.
- Productionized logic must move to `data_pipeline/src/`.
- Generated data artifacts should not be stored in `data_pipeline/notebooks/`; use `data/ingest/` and `data/transform/processed/`.
- Archived notebooks are not retained in-repo; use git history for historical notebook snapshots.
- See notebook-specific rules in `data_pipeline/notebooks/README.md`.
