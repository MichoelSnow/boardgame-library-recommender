# Data Pipeline Scripts

## `run_ingest_pipeline.py`
- What it does:
  - Orchestrates staged ingest execution:
    - `get_ranks`
    - `get_game_data` (fresh on a new run; resumes on retries)
    - `get_ratings` (incremental refresh of stale games, unless `--skip-ratings`)
  - Persists stage/run state to JSON for resume.
  - Retries failed stages up to max attempts.
  - Sends optional email notification on failure/completion.
- State file:
  - default: `/app/data/ingest/run_state.json`
  - override: `--state-path` or `INGEST_RUN_STATE_PATH`
- Log file:
  - default directory: `/app/data/logs/ingest`
  - filename: `run_ingest_pipeline_<timestamp>.log`
  - override directory: `--log-dir` or `INGEST_LOG_DIR`
- Failure behavior:
  - On max-attempt failure, the runner marks the stage `failed`, sends an alert,
    exits, and resets the attempt counter to `0`. A later invocation can retry
    the failed stage.
- Run lifecycle:
  - A completed state starts a new run on the next invocation.
  - A new run fetches fresh ranks and creates a fresh game-data DuckDB.
  - A failed or incomplete state resumes from the first incomplete stage, including the new game-data DuckDB.
  - Ratings continue from the existing ratings DuckDB and refresh only stale games.
  - Game IDs missing from an otherwise valid BGG response are logged and skipped; the stage fails at 100 skipped IDs.
  - After the game-data stage succeeds, superseded ranks CSVs, game-data DuckDB files, and orphaned WAL files are removed before ratings begins; the latest ranks and game-data files are retained.
  - `--reset-state` remains available to force a new run manually.

For a stage-only invocation, use `--only-stage` directly or use the Fly
operator commands documented below:

```bash
poetry run python scripts/data_pipeline/run_ingest_pipeline.py --only-stage get_ranks
poetry run python scripts/data_pipeline/run_ingest_pipeline.py --only-stage get_game_data
poetry run python scripts/data_pipeline/run_ingest_pipeline.py --only-stage get_ratings
```

Stage-only runs preserve the other stage states. `get_game_data` requires
completed rankings, and `get_ratings` requires completed game data.

The preferred Fly operator interface is `scripts/ingest/fly_ingest.sh`. It separates machine lifecycle from ingestion jobs:

```bash
scripts/ingest/fly_ingest.sh maintenance start --for 4h
scripts/ingest/fly_ingest.sh maintenance stop
scripts/ingest/fly_ingest.sh machine status
scripts/ingest/fly_ingest.sh machine shell

scripts/ingest/fly_ingest.sh run ranks
scripts/ingest/fly_ingest.sh run game-data
scripts/ingest/fly_ingest.sh run fresh
scripts/ingest/fly_ingest.sh run resume
scripts/ingest/fly_ingest.sh run ratings

scripts/ingest/fly_ingest.sh deploy
scripts/ingest/fly_ingest.sh secrets sync
scripts/ingest/fly_ingest.sh resize --memory 8192
scripts/ingest/fly_ingest.sh logs
scripts/ingest/fly_ingest.sh artifacts list
```

All run commands start one detached Fly process; the local terminal does not need to remain open. Maintenance is separate and must be started explicitly.
- Maintenance mode:
  - Use `scripts/ingest/fly_ingest.sh maintenance start --for 4h` to keep the machine running for SSH/manual commands without executing pipeline stages. The lease expires automatically after four hours by default.
- Example:
```bash
poetry run python scripts/data_pipeline/run_ingest_pipeline.py
poetry run python scripts/data_pipeline/run_ingest_pipeline.py --skip-ratings
poetry run python scripts/data_pipeline/run_ingest_pipeline.py --max-stage-attempts 5
```

## `profile_ingest_stage.py`
- What it does:
  - Profiles an ingest-stage command with `time -v`.
  - Writes structured JSON artifacts to `logs/profiling/data_pipeline/`.
- Naming:
  - Output file is named by profiled function and timestamp:
    - `<function>.<timestamp>.json` (example: `get_ranks.20260312T233427Z.json`)
- Output fields include:
  - `target_functions`
  - `profile_generator_function`
  - `command`
  - `started_at_utc`
  - `duration_seconds`
  - `exit_code`
  - `max_rss_kb`
  - `time_verbose_metrics`
  - `stderr_tail`
  - `stdout_tail`
  - `tails_pretty_lines` (human-readable stdout/stderr tail lines)

Example:

```bash
poetry run -- python scripts/data_pipeline/profile_ingest_stage.py \
  --target-functions data_pipeline.src.ingest.get_ranks.main \
  -- poetry run -- python -m data_pipeline.src.ingest.get_ranks
```

## `match_title_corrections.py`
- What it does:
  - Matches `data/pax/title_corrections_raw.csv` rows to BGG IDs using title/publisher/year/id evidence.
  - Prioritizes exact base-title matches (for non-expansion, non-promo rows) so sequel/variant titles do not outrank the canonical title based only on metadata signals.
  - Applies manual overrides from CSV (not notebook parsing).
  - Writes resolved output and a top-3 review queue.
- Manual fixes input:
  - default: `/mnt/c/Users/prote/Documents/ttlib_east26/new_work/data/manual_fixes.csv`
  - columns supported:
    - `title_id` or `min_titles_id` -> `bgg_id` or `new_bgg_id`
    - optional `old_bgg_id`/`source_bgg_id`/`from_bgg_id`/`bgg_id_old` -> `bgg_id` or `new_bgg_id`
- Example:
```bash
poetry run python scripts/data_pipeline/match_title_corrections.py
```

## `match_titles_to_bgg.py`
- What it does:
  - Matches a simple CSV of `title` + `publisher_name` rows to a single best BGG game per row.
  - Outputs:
    - `title`
    - `publisher_name`
    - `bgg_id`
    - `bgg_name`
    - `bgg_publishers`
    - `year_published`
  - No review queue and no top-3 candidate output.
- Input requirements:
  - Must contain columns: `title`, `publisher_name`
- Example:
```bash
poetry run python scripts/data_pipeline/match_titles_to_bgg.py \
  --input data/pax/east_2026_new_game_202603270828.csv \
  --output data/pax/east_2026_new_game_202603270828_matched.csv
```

## `build_clean_title_corrections.py`
- What it does:
  - Builds a cleaned library export from `title_corrections_with_new_bgg_id.csv`.
  - Outputs only the finalized columns needed for downstream use.
  - Applies manual-fix ground truth from `/mnt/c/Users/prote/Documents/ttlib_east26/new_work/data/manual_fixes.csv` (title_id -> bgg_id/new_bgg_id).
  - Preserves original names for title_ids listed in `/mnt/c/Users/prote/Documents/ttlib_east26/new_work/data/keep_name.csv`.
- Rules:
  - Keep original `title` and `bgg_id` when `match_confidence` is `low`/`medium` and `status != 0`.
  - Use `new_bgg_id` when `match_confidence` is `high` or `status == 0` (if `new_bgg_id` exists).
  - Manual fixes override matcher output for `bgg_id` when `title_id` appears in manual fixes.
  - For eligible rows, replace `title` with `new_bgg_name` only when similarity meets threshold.
  - Default title replacement threshold is `70`.
- Output columns:
  - `title`
  - `title_id`
  - `game`
  - `game_barcode`
  - `bgg_id`
  - `match` (title similarity score between original title and `new_bgg_name`)
  - `has_updated_title`
  - `title_original`
  - `has_updated_bgg_id`
  - `bgg_id_original`
- Example:
```bash
poetry run python scripts/data_pipeline/build_clean_title_corrections.py \
  --input data/pax/title_corrections_with_new_bgg_id.csv \
  --output data/pax/title_corrections_cleaned.csv \
  --title-match-threshold 70 \
  --title-similarity-metric token_sort
```
