# Data Pipeline

This guide describes the data workflow from collection through database import.
It is organized by decision point, not as one command sequence. Do not run
every command shown: choose one collection path and one import destination,
then run only the optional operations you need.

## Workflow map

| Goal | Use this path |
| --- | --- |
| Run the first remote ingest | Configure the Fly ingest app -> [1.B: Collect remotely on Fly](#1b-collect-remotely-on-fly-bg-lib-ingest) -> `run fresh` |
| Start a new remote ingest after a completed run | Obtain a current BGG ranks URL -> sync secrets -> [1.B: Collect remotely on Fly](#1b-collect-remotely-on-fly-bg-lib-ingest) -> `run fresh` |
| Resume a failed or interrupted remote ingest | Check status and logs -> [1.B: Collect remotely on Fly](#1b-collect-remotely-on-fly-bg-lib-ingest) -> `run resume` |
| Rerun only the ratings stage | [Fly ingest stage commands](../scripts/ingest/README.md#runs) -> `run ratings` |
| Develop or test with data on your computer | [1.A: Collect locally](#1a-collect-locally) -> [Phase 2: Process artifacts locally](#phase-2-process-artifacts-locally) -> [3.A: Import into a local database](#3a-import-into-a-local-database) |
| Run a long refresh without keeping your computer connected | [1.B: Collect remotely on Fly](#1b-collect-remotely-on-fly-bg-lib-ingest) -> [Phase 2: Process artifacts locally](#phase-2-process-artifacts-locally) |
| Update the deployed application | [1.B: Collect remotely on Fly](#1b-collect-remotely-on-fly-bg-lib-ingest) -> [Phase 2: Process artifacts locally](#phase-2-process-artifacts-locally) -> [3.B: Import into deployed Fly Postgres](#3b-import-into-deployed-fly-postgres) |
| Download completed remote artifacts | [1.B: Collect remotely on Fly](#1b-collect-remotely-on-fly-bg-lib-ingest) -> `Optional: Export artifacts to local processing` |
| Process and import a collected dataset locally | [Phase 2: Process artifacts locally](#phase-2-process-artifacts-locally) -> [3.A: Import into a local database](#3a-import-into-a-local-database) |
| Rebuild only a particular ingest stage | Use the [Fly ingest stage commands](../scripts/ingest/README.md#runs) |

Local and remote collection are alternatives. Local and remote import are also
alternatives. Library import, database reset, backups, image synchronization,
and embedding transfer are conditional operations described in their sections.

## Reference: Scope
- BoardGameGeek ingest pipeline, normalization, feature generation, and asset preparation.
- Exploratory notebooks for analysis/prototyping only.

## Reference: Directory layout
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

## Phase 1: Collect data

Use these commands from repo root.

### 1.A: Collect locally

Use this path when the workload should run locally or when debugging a stage.
Run the stages in order; the second and third commands can resume an interrupted
stage with `--continue-from-last`.

#### Required steps

1. Collect rankings:
```bash
poetry run python -m data_pipeline.src.ingest.get_ranks
```

#### Reference: Required input
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

#### Reference: Inputs and outputs

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

### 1.B: Collect remotely on Fly (`bg-lib-ingest`)

Use this path for long-running or memory-intensive collection. The ingest
machine runs independently of your terminal. Do not also run the local
collection commands for the same refresh.

Use dedicated ingest app/machine, not request-serving app machines.

#### Reference: Configuration and files

Key files:
- Fly config: `fly.ingest.toml`
- Image build: `Dockerfile.ingest`
- Orchestrator: `scripts/data_pipeline/run_ingest_pipeline.py`
- Operator interface: `scripts/ingest/fly_ingest.sh`

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
  --size 5 \
  --yes
```

#### Required steps: Run the remote ingest
1. Obtain a fresh signed BGG ranks URL:

   Log in to BGG, open `https://boardgamegeek.com/data_dumps/bg_ranks`, and copy the current ZIP link.

   Update the repo-root `.env` value:
   ```bash
   BGG_RANKS_ZIP_URL=<current_signed_bgg_ranks_zip_url>
   ```

   The signed URL is not generated by this repository and may expire. A new URL is normally required for each new full ingest run.

2. Sync the ingest secrets to Fly:
```bash
scripts/ingest/fly_ingest.sh secrets sync
```

3. Start ingest:
```bash
scripts/ingest/fly_ingest.sh run fresh
```

Deploy only for the first setup or when ingest code/configuration has changed. Deploying stops the machine; sync secrets and start it afterward:
```bash
scripts/ingest/fly_ingest.sh deploy
scripts/ingest/fly_ingest.sh secrets sync
scripts/ingest/fly_ingest.sh run fresh
```

4. Check status:
```bash
scripts/ingest/fly_ingest.sh machine status
```

5. Optional logs:
```bash
scripts/ingest/fly_ingest.sh logs
```

#### Reference: Remote run behavior
- Stage order: `get_ranks -> get_game_data -> get_ratings`
- Individual stage commands run exactly one selected stage and preserve the other stage states.
- `run game-data` requires completed rankings; `run ratings` requires completed game data.
- A new run downloads fresh ranks and creates a fresh game-data DuckDB.
- A failed or interrupted run resumes the game-data DuckDB created by that run.
- Ratings reuse the existing ratings DuckDB and refresh only games that are behind the current game-data `numratings` values.
- If BGG returns no record for an individual game ID, that ID is logged and skipped; the stage fails after 100 skipped IDs to detect broad API or data problems.
- After the game-data stage succeeds, superseded ranks CSVs, game-data DuckDB snapshots, and orphaned WAL files are removed before the long ratings stage begins; the latest ranks and game-data files are retained.
- A completed prior run starts a new run when the machine is started again.
- An incomplete or failed run resumes from its first incomplete stage.
- On repeated stage failure:
  - alert is sent (if configured)
  - stage attempts are reset to `0`
  - run exits cleanly (future runs are not blocked)
- On completion, completion alert is sent (if configured)
- Machine exits when pipeline exits (restart policy `no`)
- Orchestrator/stage logs are written under `/app/data/logs/ingest/*`

#### Operations: Maintenance mode

Use this only for SSH inspection or manual debugging. It is not part of a
normal ingest run.

1. Start the machine without running the pipeline:
```bash
scripts/ingest/fly_ingest.sh maintenance start --for 4h
```
2. SSH and run manual commands:
```bash
scripts/ingest/fly_ingest.sh machine shell
```
3. Stop machine when finished:
```bash
scripts/ingest/fly_ingest.sh maintenance stop
```

Maintenance mode is managed by the dispatcher. Normal runs should use
`run ranks`, `run game-data`, `run ratings`, `run fresh`, or `run resume`; do
not manually toggle the secret.

#### Optional: Export artifacts to local processing

This handoff is required when continuing to Phase 2 on the local machine. It is
not required if the remote artifacts will remain on Fly and no local processing
or import is planned.

If the pipeline has already finished (machine stopped), you must use maintenance mode to keep the machine up long enough to list/download files.

Start the machine in maintenance mode:
```bash
scripts/ingest/fly_ingest.sh maintenance start --for 4h
```

List remote files:
```bash
scripts/ingest/fly_ingest.sh artifacts list
```

Download (resumable + checksum verified):
```bash
# ranks -> data/ingest/ranks
scripts/ingest/fly_ingest.sh artifacts download \
  --remote-path /app/data/ingest/ranks/boardgame_ranks_<date>.csv

# game_data -> data/ingest/game_data
scripts/ingest/fly_ingest.sh artifacts download \
  --remote-path /app/data/ingest/game_data/boardgame_data_<timestamp>.duckdb \
  --chunk-mb 256

# ratings -> data/ingest/ratings
scripts/ingest/fly_ingest.sh artifacts download \
  --remote-path /app/data/ingest/ratings/boardgame_ratings_<timestamp>.duckdb \
  --chunk-mb 256
```

Stop machine when done:
```bash
scripts/ingest/fly_ingest.sh maintenance stop
```



Download notes:
- Default output dir is inferred from remote path
- Download resumes from existing chunk cache
- Final file is promoted only after SHA-256 match
- `.parts` cache is removed on success (use `--keep-parts` to retain)

## Phase 2: Process artifacts locally

These commands run locally after local collection or after remote artifacts have
been downloaded. They are not part of the Fly ingest machine run.

The normalization step is required before importing processed game data. The
feature steps are conditional: run collaborative embeddings for collaborative
recommendations, content embeddings for content or hybrid recommendations, and
both when the deployed runtime uses both feature sets.

### 2.A: Required step — Process and normalize relational outputs
```bash
poetry run python -m data_pipeline.src.transform.data_processor
```

Behavior:
- Merges ranking + detailed game data
- Normalizes relationship tables
- Writes timestamped outputs under `data/transform/processed/<timestamp>/`

### 2.B: Feature step — Generate collaborative filtering artifacts
```bash
poetry run python -m data_pipeline.src.features.create_embeddings
```

Behavior:
- Builds sparse recommendation artifacts from ratings data
- Writes embedding/mapping outputs used by backend recommender runtime

### 2.C: Feature step — Generate content-based artifacts
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

## Phase 3: Import data

This section contains two alternative destinations. Choose the local import
path when the target database is on your computer; choose the remote import
path when updating the deployed Fly application. The numbered steps within a
chosen path are ordered, but commands marked optional are not required for
every import.

### 3.A: Import into a local database

Use this path for a local/offline application. It is independent of the remote
Fly Postgres import path.

1. **Required — run migrations:**
```bash
# from repo root
poetry run alembic -c backend/alembic.ini upgrade head
```

2. **Required — import processed game data:**
```bash
poetry run python backend/app/import_data.py
```

3. **Optional — replace existing imported game data:**
```bash
poetry run python backend/app/import_data.py --delete-existing
```

4. **Optional — import library convention data:**
```bash
poetry run python backend/app/import_library_data.py --csv data/library/bg_lib_games_<timestamp>.csv
poetry run python backend/app/import_library_data.py --csv data/library/bg_lib_games_<timestamp>.csv --delete-existing
```

Notes:
- Local DB target is controlled by your local `DATABASE_URL` (SQLite fallback or Postgres).
- `import_data.py` imports latest `processed_games_*` timestamp set.
- `import_library_data.py` imports legacy `data/library/bg_lib_games_*.csv` into
  `library_imports` + `library_import_items` (not `library_games`).

### 3.B: Import into deployed Fly Postgres

Use this path when updating the deployed application. It runs inside the
target Fly app environment and does not update a local database.

Run inside the target app container so app + DB configuration match deploy environment.

Recommended execution order for remote import:
1. **Operations — start the target app and database machines** if they are stopped:
   ```bash
   scripts/deploy/fly_stack.sh dev up
   # or: scripts/deploy/fly_stack.sh prod up
   ```
   Use the environment that matches `TARGET_APP`. This starts the machines; it
   does not deploy new code or run an import.
2. **Required — stage processed data and runtime artifacts** on the target app machine (section below).
3. **Recommended — back up** the target remote database before a reset/import. Choose one backup option below; do not run both.
4. **Required — run the import** using the detached import job.
5. **Optional — import library convention data** if the library should be updated.
6. **Optional — stop the target app and database machines** when all remote work is complete and they should not remain running:
   ```bash
   scripts/deploy/fly_stack.sh dev down
   # or: scripts/deploy/fly_stack.sh prod down
   ```

Do not run the local import commands as part of this path. The reset import is
destructive and is not required when the remote import procedure is explicitly
configured for a non-reset update.

#### Required subprocedure: Stage processed data and embeddings

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

#### Recommended subprocedure: Back up the remote database (choose one option)

Both options create a logical `pg_dump` of the same target database. They differ
only in where the backup file is written:

- **Option A — save locally (recommended default):** streams the backup to the
  local machine, where it is immediately available for restore or archival.
- **Option B — save remotely:** writes the backup on the remote Fly database
  machine, which avoids transferring a large dump to the local machine but
  requires later remote-file management.

##### Option A: Save the backup locally

From repo root (local machine):
```bash
# Replace dev with prod when backing up production.
poetry run python scripts/db/fly_postgres_backup.py \
  --env dev \
  --output ".tmp/dev-before-import-$(date -u +%Y%m%dT%H%M%SZ).sql"
```

Notes:
- `scripts/db/fly_postgres_backup.py` auto-loads repo-root `.env` for `POSTGRES_USER` and `POSTGRES_DB` defaults.
- Add these optional flags only when the database credentials differ from the
  `.env` values:
```bash
poetry run python scripts/db/fly_postgres_backup.py \
  --env dev \
  --postgres-user postgres \
  --postgres-db boardgame_recommender \
  --output ".tmp/dev-before-import-$(date -u +%Y%m%dT%H%M%SZ).sql"
```

##### Option B: Save the backup on the remote database machine

Use this option instead of Option A when the dump should remain on the remote
machine or when transferring it locally is impractical.

```bash
# Set this once for the current run; use prod for production.
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

The following are follow-up operations for Option B only:

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

#### Required subprocedure: Run the remote import

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
- `start` requires a resolvable machine with `autostop=stop`, temporarily sets `autostop=off`, starts the machine if needed, and waits for it to reach `started` before opening SSH. A local watcher restores `autostop=stop` after import completion, interruption, or its four-hour safety timeout.
- `status` is read-only and does not modify machine settings; it prints machine service policy (`autostop`/`autostart`) and local watcher status.
- `stop` is an explicit fallback that force-restores machine `autostop=stop`.
- If the machine ID or existing autostop mode cannot be determined, `start` refuses to run rather than leaving an untracked override.
- Keep the local terminal host running while the detached import is active so the watcher can restore autostop promptly; timeout restoration is a safety net.

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

#### Optional: Import library convention data

Run this only if the library should be updated. It imports into
`library_imports` + `library_import_items` and is separate from the processed
game-data import.

```bash
# dev
fly ssh console -a "${FLY_APP_NAME_DEV}" -C \
  'sh -lc "cd /app/backend && poetry run python app/import_library_data.py --csv /data/library/bg_lib_games_<timestamp>.csv"'

# prod
fly ssh console -a "${FLY_APP_NAME_PROD}" -C \
  'sh -lc "cd /app/backend && poetry run python app/import_library_data.py --csv /data/library/bg_lib_games_<timestamp>.csv"'
```

## Operations and reference

### 4.A: Optional operation — Seed images to Fly volumes

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

### 4.B: Reference — Notebook policy
- Notebooks are allowed only under `data_pipeline/notebooks/`.
- No secrets/credentials/tokens in notebook source or outputs.
- Productionized logic must move to `data_pipeline/src/`.
- Generated data artifacts should not be stored in `data_pipeline/notebooks/`; use `data/ingest/` and `data/transform/processed/`.
- Archived notebooks are not retained in-repo; use git history for historical notebook snapshots.
- See notebook-specific rules in `data_pipeline/notebooks/README.md`.
