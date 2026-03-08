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

### DuckDB Ratings Backend

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

## Notebook Policy
- Notebooks are allowed only under `data_pipeline/notebooks/`.
- No secrets/credentials/tokens in notebook source or outputs.
- Productionized logic must move to `data_pipeline/src/`.
- Generated data artifacts should not be stored in `data_pipeline/notebooks/`; use `data/pipeline/`.
- Archived notebooks are not retained in-repo; use git history for historical notebook snapshots.
- See notebook-specific rules in `data_pipeline/notebooks/README.md`.
