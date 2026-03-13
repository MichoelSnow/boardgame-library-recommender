# Data Pipeline Scripts

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
