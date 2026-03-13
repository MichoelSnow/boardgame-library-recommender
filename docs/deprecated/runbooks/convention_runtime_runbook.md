# Convention Runtime Runbook

This section defines the operational flow for convention runtime profile switching.

## Target Profiles
- `standard`:
  - default profile
  - cost-optimized warm settings (`min_machines_running=0`)
- `convention`:
  - active event profile for `prod`
  - one always-running machine (`min_machines_running=1`)
  - `Gunicorn` + `3` Uvicorn workers
  - `GUNICORN_CMD_ARGS="--timeout 90"`
- `rehearsal`:
  - temporary `dev` profile for load testing
  - mirrors `convention` process model and warm settings

## Event Schedule Configuration (Per Convention)
Set these values per event/city before using convention profile scheduling:
- `CONVENTION_TIMEZONE` (IANA timezone, for example `America/New_York`, `Europe/Berlin`)
- `CONVENTION_WARM_START` (local event time, `HH:MM`)
- `CONVENTION_WARM_END` (local event time, `HH:MM`)

Example:
```bash
fly secrets set \
  CONVENTION_TIMEZONE="America/New_York" \
  CONVENTION_WARM_START="09:00" \
  CONVENTION_WARM_END="00:00" \
  -a bg-lib-app
```

## Profile Config Files
- `fly.toml` (prod standard)
- `fly.convention.toml` (prod convention)
- `fly.dev.toml` (dev standard)
- `fly.dev.rehearsal.toml` (dev rehearsal)

## Planned Enable/Disable Flow (Prod)
1. Enable convention profile:
```bash
fly deploy -a bg-lib-app -c fly.convention.toml
```
2. Verify profile:
```bash
fly status -a bg-lib-app
fly checks list -a bg-lib-app
curl -fsS https://bg-lib-app.fly.dev/api
```
3. Record convention profile enable event in deploy traceability:
```bash
poetry run python scripts/deploy/record_deploy_traceability.py --env prod --marker convention-profile-enable
```
4. Disable convention profile (return to standard):
```bash
fly deploy -a bg-lib-app -c fly.toml
```
5. Verify standard profile:
```bash
fly status -a bg-lib-app
fly checks list -a bg-lib-app
curl -fsS https://bg-lib-app.fly.dev/api
```
6. Record convention profile disable event in deploy traceability:
```bash
poetry run python scripts/deploy/record_deploy_traceability.py --env prod --marker convention-profile-disable
```

## Planned Enable/Disable Flow (Dev Rehearsal)
1. Enable rehearsal profile:
```bash
fly deploy -a bg-lib-app-dev -c fly.dev.rehearsal.toml
```
2. Run rehearsal/load-test checks.
3. Disable rehearsal profile (return to standard dev):
```bash
fly deploy -a bg-lib-app-dev -c fly.dev.toml
```

## Rehearsal Baseline (Recorded 2026-03-06)
- `VUS=10`, mixed profile, `3m`:
  - `http_req_failed=0.00%`
  - `http_req_duration p95=165.81ms`
  - `games_duration p95=213.29ms`
  - `recommendation_duration p95=198.45ms`
- `VUS=30`, mixed profile, `3m`:
  - `http_req_failed=0.00%`
  - `http_req_duration p95=181.29ms`
  - `games_duration p95=202.76ms`
  - `recommendation_duration p95=284.80ms`

## Rollback Rule
- If health checks fail or latency regresses unexpectedly after a profile switch:
  - redeploy the previous profile config immediately
  - run core validation checks
  - record the event and recovery action in release/deploy notes
