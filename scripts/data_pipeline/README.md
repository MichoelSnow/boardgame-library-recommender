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

## PAX labeling

PAX title/BGG reconciliation is a domain-specific workflow rather than a
general pipeline stage. See [`scripts/pax_labeling/README.md`](../pax_labeling/README.md)
for the workflow, input contracts, and commands.
