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

## Data Collection and Processing

The pipeline uses a staged ingest flow from BoardGameGeek. Run commands from repo root with `poetry run python ...`.

### 1) Collect Board Game Rankings

```bash
poetry run python -m data_pipeline.src.ingest.get_ranks
```

Behavior:
- Downloads ranks from a user-provided signed BGG ZIP URL.
- Downloads rankings for board games.
- Writes rank snapshot(s) under `data/ingest/ranks/` (timestamped files).

Required input:
- `--ranks-zip-url "<signed-url>"` or `BGG_RANKS_ZIP_URL` in environment.
- To obtain the signed URL:
  1. log in to BoardGameGeek
  2. open `https://boardgamegeek.com/data_dumps/bg_ranks`
  3. copy the current boardgame ranks ZIP link from that page

Example:

```bash
poetry run python -m data_pipeline.src.ingest.get_ranks --ranks-zip-url "<signed-url>"
```

### 2) Collect Detailed Game Data

```bash
poetry run python -m data_pipeline.src.ingest.get_game_data
```

Behavior:
- Processes game IDs in BGG API-sized batches (`20` IDs/request).
- Fetches metadata, stats, poll info, links, and version data.
- Writes `boardgame_data_<timestamp>.duckdb` under `data/ingest/game_data/`.
- Resume mode (`--continue-from-last`) reuses the latest DuckDB store and skips completed game IDs.

Required input:
- `BGG_TOKEN` token, sent as `Authorization: Bearer <token>`.
  - The script first checks process env.
  - If missing, it auto-loads repo-root `.env` and retries.

Resume mode:

```bash
poetry run python -m data_pipeline.src.ingest.get_game_data --continue-from-last
```

### 3) Collect User Ratings

```bash
poetry run python -m data_pipeline.src.ingest.get_ratings
```

Behavior:
- Crawls ratings pages for games with sufficient ratings.
- Persists raw ratings incrementally to DuckDB during crawling.

Required input:
- `BGG_TOKEN` token, sent as `Authorization: Bearer <token>`.
  - The script first checks process env.
  - If missing, it auto-loads repo-root `.env` and retries.

Artifacts:
- DuckDB store(s): `data/ingest/ratings/boardgame_ratings_<timestamp>.duckdb`

Resume mode:

```bash
poetry run python -m data_pipeline.src.ingest.get_ratings --continue-from-last
```

### 3a) DuckDB Ratings Backend

The ratings crawler uses DuckDB as a persistent crawl-time store.

- Location pattern: `data/ingest/ratings/boardgame_ratings_<timestamp>.duckdb`
- Table: `boardgame_ratings(game_id BIGINT, rating_round DOUBLE, username TEXT)`
- Index: `idx_boardgame_ratings` on `(game_id, rating_round, username)`

Notes:
- Inserts are de-duplicated during crawl.
- Resume mode prefers the DuckDB-backed state when present.

### 4) Process and Normalize Data

```bash
poetry run python -m data_pipeline.src.transform.data_processor
```

Behavior:
- Merges ranking and detailed game data.
- Normalizes relationships (mechanics, categories, designers, artists, publishers, families, expansions, integrations, implementations, compilations, versions, language dependence, suggested players).
- Writes timestamped CSV outputs in `data/transform/processed/<timestamp>/` using `processed_games_*` naming.

### 5) Generate Collaborative Filtering Artifacts

```bash
poetry run python -m data_pipeline.src.features.create_embeddings
```

Behavior:
- Builds sparse recommendation artifacts from ratings data.
- Writes embedding + mapping outputs used by the backend recommendation engine.

## Running Ingest on Fly (`bg-lib-ingest`)

Use the dedicated ingest app instead of request-serving app machines.

Files:
- Fly config: `fly.ingest.toml`
- Image build: `Dockerfile.ingest`
- Orchestrator: `scripts/data_pipeline/run_ingest_pipeline.py`
- Deploy/start/status helpers:
  - `scripts/deploy/fly_ingest_deploy.sh`
  - `scripts/deploy/fly_ingest_start.sh`
  - `scripts/deploy/fly_ingest_status.sh`

Machine profile:
- `shared-cpu-4x`
- `2GB` RAM
- volume mounted at `/app/data`

Run flow:
1. Create ingest app (one-time):
```bash
fly apps create "${FLY_APP_NAME_INGEST:-bg-lib-ingest}"
```
2. Create ingest volume (one-time):
```bash
fly volumes create bg_lib_ingest_data \
  --app "${FLY_APP_NAME_INGEST:-bg-lib-ingest}" \
  --region iad \
  --size 4 \
  --yes
```
3. Deploy ingest app image (the deploy script will stop the machine after deploy):
```bash
scripts/deploy/fly_ingest_deploy.sh
```
4. Populate `.env` (Brevo + ingest):
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
5. Sync secrets from `.env` to Fly:
```bash
scripts/deploy/fly_ingest_set_secrets.sh
```
6. Start run manually (this is what actually starts ingestion):
```bash
scripts/deploy/fly_ingest_start.sh
```
7. Check status:
```bash
scripts/deploy/fly_ingest_status.sh
```
8. Optional: tail logs in real time:
```bash
# Ingest machine orchestrator + stage logs
fly logs -a "${FLY_APP_NAME_INGEST:-bg-lib-ingest}"

# Current run-state snapshot
fly ssh console -a "${FLY_APP_NAME_INGEST:-bg-lib-ingest}" -C "cat /app/data/ingest/run_state.json"
```
9. List available remote ingest artifacts:
```bash
scripts/deploy/fly_ingest_list_artifacts.sh
```
10. Download large ingest artifacts back to local (resumable + checksum verified):
```bash
# Example: ranks CSV (downloads to data/ingest/ranks by default)
scripts/deploy/fly_ingest_download_artifact.sh \
  --remote-path /app/data/ingest/ranks/boardgame_ranks_<date>.csv

# Example: game-data DuckDB
scripts/deploy/fly_ingest_download_artifact.sh \
  --remote-path /app/data/ingest/game_data/boardgame_data_<timestamp>.duckdb \
  --chunk-mb 256

# Example: ratings DuckDB
scripts/deploy/fly_ingest_download_artifact.sh \
  --remote-path /app/data/ingest/ratings/boardgame_ratings_<timestamp>.duckdb \
  --chunk-mb 256
```

Notes:
- The orchestrator runs stages in order: `get_ranks` -> `get_game_data` -> `get_ratings`.
- `get_game_data` and `get_ratings` always run with `--continue-from-last`.
- On repeated stage failure (max attempts), a failure notification is sent (if configured), stage attempts are reset to `0`, and the run exits.
- On completion, a completion notification is sent (if configured).
- The machine exits when pipeline exits; with restart policy `no`, it stays stopped until manually started again.
- Logs are written in real time to:
  - orchestrator: `/app/data/logs/ingest/run_ingest_pipeline_<timestamp>.log`
  - stage scripts: `/app/data/logs/ingest/stages/get_ranks.log`, `/app/data/logs/ingest/stages/get_game_data.log`, `/app/data/logs/ingest/stages/get_ratings.log`
- Download helper behavior for large files:
  - if `--output-dir` is omitted, default local destinations are:
    - ranks -> `data/ingest/ranks`
    - game data -> `data/ingest/game_data`
    - ratings -> `data/ingest/ratings`
  - stores chunk cache in selected destination as `.<filename>.parts/`
  - rerun with same args to resume from prior completed chunks
  - computes remote and local SHA-256 and only finalizes output on exact match
  - removes `.parts` after successful verified download (use `--keep-parts` to retain)
- Maintenance mode for manual SSH/debug:
  - set secret `INGEST_MAINTENANCE_MODE=true`
  - start machine
  - SSH/run manual commands
  - unset `INGEST_MAINTENANCE_MODE` before normal ingest runs

## Importing Data to Backend

Before importing locally, ensure schema is current:

```bash
poetry run alembic upgrade head
```

Import latest processed datasets:

```bash
poetry run python backend/app/import_data.py
```

Behavior:
- Finds latest processed `processed_games_*` timestamp set.
- Imports games plus normalized relation tables.
- Processes in batches and logs progress to `logs/import_data.log`.

Optional reset import:

```bash
poetry run python backend/app/import_data.py --delete-existing
```

### Library Convention Data Import

```bash
poetry run python backend/app/import_library_data.py
```

Behavior:
- Loads latest `library_games_*.csv` from `data/library/`.
- Imports Library rows and links to `BoardGame` records via BGG ID where available.
- Enables Library-specific filtering paths in the API/UI.
- Logs progress to `logs/import_library_data.log`.

Optional reset import:

```bash
poetry run python backend/app/import_library_data.py --delete-existing
```

## Operational Policy (Phase 11, Discussion Draft)

Status:
- This section is a proposal set for review, not final policy.
- Nothing here is binding until explicitly approved and reflected in the migration checklist as complete.

### Proposed Idempotency and Retry Strategy
- Write endpoints (application API), proposed:
  - Do not assume write requests are safe to blindly replay.
  - Default policy is no automatic client-side retries for write operations unless endpoint-level idempotency keys are explicitly introduced.
- Ingestion and import jobs, proposed:
  - Ingestion stages write timestamped outputs and are safe to rerun.
  - Import jobs are operationally idempotent via rerun + latest-timestamp selection, with optional `--delete-existing` for full reset flows.
  - Retries should target transient network/transport failures only, not schema/data-contract failures.

### Proposed Timeout and Retry Policy
- External calls (BGG/API/network), proposed:
  - Use explicit timeouts and bounded retries with exponential backoff.
  - Keep retry counts low (for example 3-5 attempts) to avoid runaway jobs.
  - Fail fast on deterministic errors (4xx, parse/schema contract failures, invalid credentials).
- Long-running jobs, proposed:
  - Run as resumable stages (`--continue-from-last` where supported).
  - Persist partial state/artifacts per stage so recovery is restart-from-stage, not ad hoc in-memory recovery.

### Proposed Fly Execution Topology
- Heavy pipeline jobs run outside the serving app machines.
- Proposed policy:
  - Do not run full ingest/transform/features jobs on production app machines.
  - Preferred execution path is local/CI/manual-ops pipeline runs, then import/sync runtime-consumed artifacts.
  - Revisit dedicated worker app only if monthly runtime or data size makes current approach unreliable.

### Proposed Monthly Rebuild Cadence and Ownership
- Cadence, proposed:
  - Run one full pipeline rebuild per month, outside request-serving paths.
- Trigger, proposed:
  - Manual operator trigger (repository owner) using documented pipeline commands.
- Owner, proposed:
  - Repository maintainer (single-owner model).
- Minimum monthly acceptance checks, proposed:
  - pipeline stages complete successfully
  - `import_data.py` succeeds
  - recommendation artifacts are present and pass `scripts/validate/validate_recommendation_artifacts.py`

### Proposed Artifact Storage, Retention, and Handoff
- Canonical locations, proposed:
  - Raw/intermediate ingest outputs: `data/ingest/`
  - Processed relational outputs for import: `data/transform/processed/`
  - Runtime recommendation artifacts: `${DATABASE_DIR}` (default `backend/database/`, Fly runtime typically `/data`)
- Retention/cleanup, proposed:
  - Keep latest successful monthly set as canonical.
  - Remove stale intermediate snapshots older than 30 days unless required for active investigation.
  - Do not commit generated pipeline/runtime artifacts to source control.
- Runtime handoff path, proposed:
  1. generate pipeline outputs
  2. run import (`backend/app/import_data.py`, optional `import_library_data.py`)
  3. validate runtime artifacts/health (`scripts/validate/validate_recommendation_artifacts.py`, API health endpoints)

## Image Seeding to Fly Volumes (Primary)

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
poetry run python backend/app/import_library_data.py --sync-images
```

## Notebook Policy
- Notebooks are allowed only under `data_pipeline/notebooks/`.
- No secrets/credentials/tokens in notebook source or outputs.
- Productionized logic must move to `data_pipeline/src/`.
- Generated data artifacts should not be stored in `data_pipeline/notebooks/`; use `data/ingest/` and `data/transform/processed/`.
- Archived notebooks are not retained in-repo; use git history for historical notebook snapshots.
- See notebook-specific rules in `data_pipeline/notebooks/README.md`.
