# Alert Scripts

## `run_prod_health_alerts.py`
- What it does:
  - Runs P0 production health checks (`/api`, DB-backed query path, recommendation status).
  - Evaluates sustained latency breaches with consecutive-run gating (default: 3 checks).
  - Emits recovery notices when previously active major alerts clear.
  - Exits non-zero on unhealthy conditions so GitHub Actions failure notifications trigger.
  - Skips checks unless `convention_mode` is active.
- When to use:
  - Scheduled via `.github/workflows/prod-health-alerts.yml`.
  - Manually for dry-run verification.
- How to use:
```bash
poetry run python scripts/alerts/run_prod_health_alerts.py --env prod
poetry run python scripts/alerts/run_prod_health_alerts.py --env prod --dry-run
```
- Notes:
  - Baseline alert delivery is GitHub Actions failure notifications.
