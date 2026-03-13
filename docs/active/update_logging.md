Best practice here is **by purpose + date**, not by source directory.

Recommended structure:
- `logs/app/` for backend runtime logs
- `logs/pipeline/` for ingest/transform/features runs
- `logs/profiling/` for profiler artifacts
- `logs/diagnostics/` for one-off failure captures (screenshots/html)
- `logs/validation/` for validation script outputs

Then within each:
- date partitioning: `YYYY-MM/` (or `YYYY-MM-DD/` if high volume)
- filenames include: `script_or_flow + timestamp + optional status`

Example:
- `logs/pipeline/2026-03/get_ranks.20260313T101500Z.log`
- `logs/diagnostics/2026-03/get_ranks_login_failure.20260313T101512Z.html`
- `logs/profiling/data_pipeline/get_ranks.20260313T101530Z.json`

Why this works:
- easy human browsing
- avoids coupling logs to code layout changes
- makes retention cleanup simple (delete old date folders)
- keeps operational intent clear

If you want, next step would be to define this as a short logging convention doc and then gradually align scripts (no big-bang move).