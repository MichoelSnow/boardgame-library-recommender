# Alert Scripts

## `check_fly_machines.py`
- What it does:
  - Discovers every app in the Fly organization through the Fly Machines API.
  - Discovers every machine in each app without storing app or machine IDs in Git.
  - Exits non-zero when a machine is in any state other than `stopped` or `destroyed`.
  - Exits non-zero when the Fly API cannot be queried, so a monitoring failure is visible.
- When to use:
  - Scheduled every six hours by `.github/workflows/fly-machine-alerts.yml`.
  - Run manually from GitHub Actions after setting the required repository variable.
- Required GitHub configuration:
  - Existing `FLY_API_TOKEN` repository or organization secret.
  - `FLY_ORG_SLUG` repository variable, such as `personal` or the Fly organization slug.
- How to use locally:
```bash
FLY_API_TOKEN="..." FLY_ORG_SLUG="personal" \
  poetry run python scripts/alerts/check_fly_machines.py
```
- Notes:
  - The schedule is expressed in UTC and GitHub Actions may start scheduled jobs a few minutes late.
  - The workflow intentionally has no alert dedupe: each scheduled run fails while a non-stopped machine is present.
  - GitHub Actions workflow-failure notifications are the delivery channel.

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
