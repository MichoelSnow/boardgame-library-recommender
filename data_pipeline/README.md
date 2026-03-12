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
  - `r2_sync.py`
  - `sync_r2_images.py`
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
- Authenticates with BoardGameGeek (when credentials are provided).
- Downloads rankings for board games.
- Writes rank snapshot(s) under `data/pipeline/` (timestamped files).

### 2) Collect Detailed Game Data

```bash
poetry run python -m data_pipeline.src.ingest.get_game_data
```

Behavior:
- Processes game IDs in BGG API-sized batches (`20` IDs/request).
- Fetches metadata, stats, poll info, links, and version data.
- Writes `boardgame_data_<timestamp>.parquet` under `data/pipeline/`.

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
- Exports a Parquet snapshot for downstream processing when complete.

Artifacts:
- DuckDB store: `data/pipeline/ratings.duckdb`
- Snapshot: `data/pipeline/boardgame_ratings_<timestamp>.parquet`

Resume mode:

```bash
poetry run python -m data_pipeline.src.ingest.get_ratings --continue-from-last
```

### 3a) DuckDB Ratings Backend

The ratings crawler uses DuckDB as a persistent crawl-time store.

- Location: `data/pipeline/ratings.duckdb`
- Table: `boardgame_ratings(game_id BIGINT, rating_round DOUBLE, username TEXT)`
- Index: `idx_boardgame_ratings` on `(game_id, rating_round, username)`

Notes:
- Inserts are de-duplicated during crawl.
- Final Parquet snapshot preserves downstream pipeline compatibility.
- Resume mode prefers the DuckDB-backed state when present.

### 4) Process and Normalize Data

```bash
poetry run python -m data_pipeline.src.transform.data_processor
```

Behavior:
- Merges ranking and detailed game data.
- Normalizes relationships (mechanics, categories, designers, artists, publishers, families, expansions, integrations, implementations, compilations, versions, language dependence, suggested players).
- Writes timestamped CSV outputs in `data/processed/` using `processed_games_*` naming.

### 5) Generate Collaborative Filtering Artifacts

```bash
poetry run python -m data_pipeline.src.features.create_embeddings
```

Behavior:
- Builds sparse recommendation artifacts from ratings data.
- Writes embedding + mapping outputs used by the backend recommendation engine.

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

### PAX Convention Data Import

```bash
poetry run python backend/app/import_pax_data.py
```

Behavior:
- Loads latest `pax_tt_games_*.csv` from `data/pax/`.
- Imports PAX rows and links to `BoardGame` records via BGG ID where available.
- Enables PAX-specific filtering paths in the API/UI.
- Logs progress to `logs/import_pax_data.log`.

Optional reset import:

```bash
poetry run python backend/app/import_pax_data.py --delete-existing
```

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
poetry run python -m data_pipeline.src.assets.sync_fly_images --scope pax-only
poetry run python -m data_pipeline.src.assets.sync_fly_images --scope top-rank-only --max-rank 10000
```

Dry-run:

```bash
poetry run python -m data_pipeline.src.assets.sync_fly_images --scope all-qualified --max-rank 10000 --dry-run
```

For Fly machine commands (dev/prod `fly ssh` usage), file counts, and validation:
- [docs/core/convention_ops.md](../docs/core/convention_ops.md)

## Cloudflare R2 Path (Deprecated Backup-Only)

This path is retained only for rollback/contingency operations.
Do not use it as the default workflow.

Canonical object keys use `games/<bgg_id>.<ext>` (for example `games/224517.jpg`).

Required environment variables:

```env
R2_ENDPOINT_URL=<cloudflare-r2-s3-endpoint>
R2_ACCESS_KEY_ID=<r2-access-key-id>
R2_SECRET_ACCESS_KEY=<r2-secret-access-key>
R2_BUCKET_NAME=<single-shared-r2-bucket-name>
R2_REGION=auto
# optional:
R2_PUBLIC_BASE_URL=<cdn-base-url>
```

R2 sync command:

```bash
poetry run python -m data_pipeline.src.assets.sync_r2_images --scope all-qualified --max-rank 10000
```

R2 behavior notes:
- Existing R2 objects are prefetched by default from `games/` and skipped without download.
- If prefetch fails, the script falls back to per-ID existence checks.
- Images are not re-downloaded when already present unless `--overwrite-existing` is passed.

Optional flags and scopes:

```bash
poetry run python -m data_pipeline.src.assets.sync_r2_images --no-prefetch-existing
poetry run python -m data_pipeline.src.assets.sync_r2_images --scope pax-only
poetry run python -m data_pipeline.src.assets.sync_r2_images --scope top-rank-only --max-rank 10000
poetry run python -m data_pipeline.src.assets.sync_r2_images --dry-run --scope all-qualified --max-rank 10000
```

Import integration commands:

```bash
# Primary path (Fly-local)
poetry run python backend/app/import_data.py --sync-images --sync-images-backend fly_local --sync-images-max-rank 10000
poetry run python backend/app/import_pax_data.py --sync-images --sync-images-backend fly_local

# Backup path (R2)
poetry run python -m data_pipeline.src.assets.download_images --sync-r2
poetry run python backend/app/import_data.py --sync-images --sync-images-backend r2_cdn --sync-images-max-rank 10000
poetry run python backend/app/import_pax_data.py --sync-images --sync-images-backend r2_cdn
```

Compatibility note:
- `--sync-images-r2` is still accepted as a legacy alias and maps to `--sync-images --sync-images-backend r2_cdn`.

## Notebook Policy
- Notebooks are allowed only under `data_pipeline/notebooks/`.
- No secrets/credentials/tokens in notebook source or outputs.
- Productionized logic must move to `data_pipeline/src/`.
- Generated data artifacts should not be stored in `data_pipeline/notebooks/`; use `data/pipeline/`.
- Archived notebooks are not retained in-repo; use git history for historical notebook snapshots.
- See notebook-specific rules in `data_pipeline/notebooks/README.md`.
