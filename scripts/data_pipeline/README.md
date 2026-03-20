# Data Pipeline Scripts

## `run_ingest_pipeline.py`
- What it does:
  - Orchestrates staged ingest execution:
    - `get_ranks`
    - `get_game_data --continue-from-last`
    - `get_ratings --continue-from-last` (unless `--skip-ratings`)
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
  - On max-attempt failure, the runner sends alert, exits, and resets stage attempts to `0` so future runs are not blocked.
- Maintenance mode:
  - Set `INGEST_MAINTENANCE_MODE=true` to keep the machine running for SSH/manual commands without executing pipeline stages.
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
