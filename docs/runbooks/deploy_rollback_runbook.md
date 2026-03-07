# Deploy and Rollback Runbook

## Purpose
- Standardize deployment and rollback for the Fly `dev` and `prod` apps.
- Ensure each release is traceable to git commit + Fly release.

## Deployment Policy
- Pull requests and feature branches run CI only.
- Pushes to `main` auto-deploy to the Fly `dev` app via GitHub Actions.
- Production deploys are manual promotions using the `Fly Deploy Prod` GitHub Actions workflow after `dev` smoke checks pass.

## Versioning Policy
- Do not bump the app version on every commit or every `dev` deploy.
- Use `git_sha` and `build_timestamp` for commit-level traceability on `dev`.
- Bump the app version only for intentional `prod` releases.
- Every new `prod` deploy should increase the release version by at least one increment.
- The canonical app version source is `pyproject.toml`.

### Increment Rules
- Patch (`0.1.0` -> `0.1.1`):
  - bug fixes
  - deploy/ops hardening
  - security fixes without major user-facing workflow change
  - refactors or cleanup that are shipped to `prod`
- Minor (`0.1.0` -> `0.2.0`):
  - user-visible features
  - meaningful API additions or behavior changes
  - architecture changes that alter runtime behavior or operational expectations
  - breaking changes while still pre-`1.0`
- Major (`0.x` -> `1.0.0`):
  - only when the app is considered stable enough for a true release-ready baseline

### When To Bump
1. Finish the code for the release milestone.
2. Validate the release on `dev`.
3. Decide the next semantic version.
4. Update `pyproject.toml`.
5. Promote that exact validated SHA to `prod`.
6. Create or update the matching Git tag after the promotion succeeds.

### Tagging Rule
- Use one semantic-version tag format for production releases.
- Recommended format:
  - `v0.1.1`
- If you keep environment-specific tags, use:
  - `prod-v0.1.1`
- Fly release versions (`v37`, etc.) are infrastructure release IDs, not app versions.

## Preconditions
- `flyctl` authenticated.
- Correct app selected (`dev` or `prod`).
- Required secrets are already set in Fly.
- For Postgres-backed environments with DB autostop enabled, `DATABASE_URL` should use Flycast hostnames (for example `pax-tt-db-dev.flycast`), not `.internal` hostnames.
- Flycast private IP is allocated on each DB app used by the app:
  - `fly ips list -a pax-tt-db-dev`
  - `fly ips list -a pax-tt-db-prod`
  - If missing, allocate it:
    - `fly ips allocate-v6 --private -a pax-tt-db-dev`
    - `fly ips allocate-v6 --private -a pax-tt-db-prod`
- DB apps should remain private-only. Verify there are no public IPs:
  - `fly ips list -a pax-tt-db-dev`
  - `fly ips list -a pax-tt-db-prod`
- Treat database migrations as required on every deploy, even if a given commit appears not to change schema. This is the conservative default for this project.
- Local development also requires `.env` with `SECRET_KEY` (minimum 32 characters) before the backend will start.
- Optional but recommended for full auth smoke coverage: set environment-specific smoke-test credentials in local `.env`:
  - shared username: `SMOKE_TEST_USERNAME`
  - env-specific passwords:
    - `SMOKE_TEST_PASSWORD_LOCAL`
    - `SMOKE_TEST_PASSWORD_DEV`
    - `SMOKE_TEST_PASSWORD_PROD`
- If you want to create or recreate the smoke-test user via script, also set:
  - `ADMIN_USERNAME`
  - `ADMIN_PASSWORD`

## Quick Wake Commands
Fly machines may be stopped when idle because `auto_stop_machines = 'stop'`.
Use stack orchestration for all normal operations:

```bash
scripts/fly_stack.sh dev up
scripts/fly_stack.sh prod up
```

For cost-control shutdown:

```bash
scripts/fly_stack.sh dev down
scripts/fly_stack.sh prod down
```

Status check:

```bash
scripts/fly_stack.sh dev status
scripts/fly_stack.sh prod status
```

Fallback note:
- If a machine does not exist (for example after `fly scale count 0`), deploy that app to recreate it before running `scripts/fly_stack.sh ... up`.
- Do not use `fly scale count 0` as a temporary stop mechanism in normal operations; it destroys machines and can force recreation/re-attachment steps. Use `scripts/fly_stack.sh <env> down` for temporary shutdown.

Cross-app dependency note:
- Fly does not provide native "start app A automatically starts app B" linking across separate apps.
- Use explicit orchestration for safe ordering via `scripts/fly_stack.sh`.

## One-Time DB App (Re)Bootstrap Notes
Use this only when introducing `fly.db.*.toml` to an existing DB app or fixing an app that accidentally created duplicate machine/volume resources.

1. Inspect current DB resources:
```bash
fly machines list -a pax-tt-db-dev
fly volumes list -a pax-tt-db-dev
```
2. Keep the intended data volume (for example `pg_data_dev`) and delete unintended duplicate machine/volume resources first.
3. If you need deterministic re-attachment to an existing volume and there is no live traffic:
   - stop stack: `scripts/fly_stack.sh dev down`
   - destroy old DB machine (volume is retained): `fly machine destroy <DB_MACHINE_ID> -a pax-tt-db-dev`
   - ensure only the intended volume remains in `fly volumes list`
   - deploy DB config: `fly deploy -a pax-tt-db-dev -c fly.db.dev.toml`
4. Re-verify:
```bash
fly machines list -a pax-tt-db-dev
fly volumes list -a pax-tt-db-dev
fly ips list -a pax-tt-db-dev
```
5. Repeat the same pattern for `prod` with `pax-tt-db-prod` and `fly.db.prod.toml`.

## DB Keepalive (App-Driven)
To keep DB machines aligned with app runtime without a 24/7 external scheduler:
- app runtime sends periodic lightweight DB pings while app machine is running
- when app machine stops, keepalive stops automatically
- DB autostop handles idle shutdown when no traffic remains

Runtime settings (configured in Fly app profiles):
- `DB_KEEPALIVE_ENABLED=true`
- `DB_KEEPALIVE_INTERVAL_SECONDS=60`

Notes:
- Keepalive does not generate inbound app traffic and does not prevent app autostop.
- Keepalive is only enabled for Postgres-backed runtime.

## Convention Runtime Profile (Phase 4B Skeleton)
This section defines the intended operational flow for convention runtime profile switching.
Use it as the implementation target for Phase 4B.

### Target Profiles
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

### Event Schedule Configuration (Per Convention)
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
  -a pax-tt-app
```

### Profile Config Files
- `fly.toml` (prod standard)
- `fly.convention.toml` (prod convention)
- `fly.dev.toml` (dev standard)
- `fly.dev.rehearsal.toml` (dev rehearsal)

### Planned Enable/Disable Flow (Prod)
1. Enable convention profile:
```bash
fly deploy -a pax-tt-app -c fly.convention.toml
```
2. Verify profile:
```bash
fly status -a pax-tt-app
fly checks list -a pax-tt-app
curl -fsS https://pax-tt-app.fly.dev/api
```
3. Disable convention profile (return to standard):
```bash
fly deploy -a pax-tt-app -c fly.toml
```
4. Verify standard profile:
```bash
fly status -a pax-tt-app
fly checks list -a pax-tt-app
curl -fsS https://pax-tt-app.fly.dev/api
```

### Planned Enable/Disable Flow (Dev Rehearsal)
1. Enable rehearsal profile:
```bash
fly deploy -a pax-tt-app-dev -c fly.dev.rehearsal.toml
```
2. Run rehearsal/load-test checks.
3. Disable rehearsal profile (return to standard dev):
```bash
fly deploy -a pax-tt-app-dev -c fly.dev.toml
```

### Rehearsal Baseline (Recorded 2026-03-06)
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

### Rollback Rule
- If health checks fail or latency regresses unexpectedly after a profile switch:
  - redeploy the previous profile config immediately
  - run core validation checks
  - record the event and recovery action in release/deploy notes

## Deploy to Dev
This is the normal path for `main` branch changes.

1. Merge to `main`.
2. GitHub Actions automatically runs `Fly Deploy Dev`.
3. Ensure required `dev` stack is started:
```bash
scripts/fly_stack.sh dev up
```
4. Run the database migration on the deployed dev app:
```bash
fly ssh console -a pax-tt-app-dev -C 'sh -lc "cd /app/backend && poetry run alembic upgrade head"'
```
5. Verify release version:
```bash
fly releases -a pax-tt-app-dev | head -n 5
```

## Validate Dev (After Every Successful Merge to `main`)
Run this after each successful merge to `main` once the `Fly Deploy Dev` workflow finishes.

1. Ensure required `dev` stack is started:
```bash
scripts/fly_stack.sh dev up
```
2. Run the database migration on the deployed dev app:
```bash
fly ssh console -a pax-tt-app-dev -C 'sh -lc "cd /app/backend && poetry run alembic upgrade head"'
```
3. Run the core validation script:
```bash
poetry run python scripts/validate_dev_deploy.py
```
4. Confirm the database migration step completed successfully before treating the deploy as valid.
5. Confirm the script reports all of the following:
- `/api` responded with the expected message
- deployed `git_sha` matches `main`
- `build_timestamp` is populated
- Fly health checks are configured and passing
- unauthenticated access is rejected on protected endpoints
- if `SMOKE_TEST_USERNAME` and `SMOKE_TEST_PASSWORD_DEV` are set, the positive login flow succeeds
- recommendation artifact files exist in `/data`
- at least one matched artifact timestamp pair exists
- the recommendation endpoint returns non-empty results for the canonical smoke-test game (`224517`)
- latency thresholds pass for `/api`, `/api/version`, and the canonical recommendation endpoint
6. The script also records the validated SHA at `.tmp/validated_dev_sha.txt` for the prod promotion step.
7. Additional manual checks are only required when the merge affects the related area:
- if frontend behavior changed: open the dev site in a browser and verify the main UI loads plus the affected flow renders correctly
- if auth changed: manually test the full login, current-user flow, and password change path as applicable (the scripted auth smoke is intentionally lightweight)
- if deployment/config changed: review Fly logs and confirm startup logs show the app loaded a matched embeddings/mapping pair successfully
8. If validation passes and the change is intended for release, continue to **Promote to Prod (Default)** below using the validated SHA.
9. If validation fails, fix forward on a new branch or roll back the dev deployment path as needed before promoting anything to prod.

## Promote to Prod (Default)
This is the canonical production deploy path.

1. Complete the dev validation steps. The validated SHA will be stored automatically at `.tmp/validated_dev_sha.txt`.
2. Display the validated SHA and use that exact value for the production promotion:
```bash
cat .tmp/validated_dev_sha.txt
```
3. Open GitHub Actions.
4. Select `Fly Deploy Prod`.
5. Click `Run workflow`.
6. Set `git_ref` to the exact validated commit SHA from `.tmp/validated_dev_sha.txt` (not just `main` unless you have confirmed they are identical).
7. Wait for the workflow to complete successfully.
8. Ensure required `prod` stack is started:
```bash
scripts/fly_stack.sh prod up
```
9. Run the database migration on the deployed prod app:
```bash
fly ssh console -a pax-tt-app -C 'sh -lc "cd /app/backend && poetry run alembic upgrade head"'
```
10. Verify the database migration completed successfully before treating the production deploy as valid.
11. Verify the new Fly release exists:
```bash
fly releases -a pax-tt-app | head -n 5
```
12. Run the core production validation script:
```bash
poetry run python scripts/validate_prod_release.py
```
13. Confirm the script reports all of the following:
- `/api` responded with the expected message
- deployed `git_sha` matches the validated SHA from `.tmp/validated_dev_sha.txt`
- `build_timestamp` is populated
- Fly health checks are configured and passing
- unauthenticated access is rejected on protected endpoints
- if `SMOKE_TEST_USERNAME` and `SMOKE_TEST_PASSWORD_PROD` are set, the positive login flow succeeds
- recommendation artifact files exist in `/data`
- at least one matched artifact timestamp pair exists
- the recommendation endpoint returns non-empty results for the canonical smoke-test game (`224517`)
- latency thresholds pass for `/api`, `/api/version`, and the canonical recommendation endpoint
- deploy traceability is recorded locally in `logs/deploy_traceability.jsonl`
- a valid rollback target is resolved and the exact rollback command is printed
14. Additional manual checks are only required when the release affects the related area:
- if frontend behavior changed: open `https://pax-tt-app.fly.dev` and verify the main UI plus the changed user flow render correctly
- if auth changed: manually test the full login, current-user flow, and password change path as applicable in `prod` (the scripted auth smoke is intentionally lightweight)
- if deployment/config changed: review `fly logs -a pax-tt-app` and confirm startup logs show the app loaded a matched embeddings/mapping pair successfully
15. If any production validation step fails, stop and either fix forward immediately or run the rollback steps below.

## Periodic Prod Alerting
- Scheduled production P0 health alerting is implemented via:
  - `.github/workflows/prod-health-alerts.yml`
  - `scripts/run_prod_health_alerts.py`
- Workflow cadence:
  - every 20 minutes
  - plus manual trigger (`workflow_dispatch`)
- Convention-mode gate:
  - workflow exits cleanly when `CONVENTION_MODE` is not active
- Default notification path:
  - GitHub Actions failure notifications (no extra services required)
- Optional email provider secrets (only if you want provider-based alert emails):
  - `ALERT_EMAIL_TO`
  - `ALERT_EMAIL_FROM`
  - `RESEND_API_KEY` (preferred)
  - `SENDGRID_API_KEY` (fallback)

## Local Emergency Fallback Deploy
Use this only if the GitHub Actions workflow is unavailable and you need to deploy manually.

```bash
scripts/fly_deploy.sh prod
```

For a local manual deploy to dev:

```bash
scripts/fly_deploy.sh dev
```

After either manual deploy, run the required migration before validation:

```bash
fly ssh console -a pax-tt-app-dev -C 'sh -lc "cd /app/backend && poetry run alembic upgrade head"'
fly ssh console -a pax-tt-app -C 'sh -lc "cd /app/backend && poetry run alembic upgrade head"'
```

## Post-Deploy Smoke Checks
1. Check health:
```bash
curl -fsS https://<APP_HOST>/api
```

2. Verify build metadata:
```bash
curl -fsS https://<APP_HOST>/api/version
```

Expected:
- `git_sha` matches deployed commit.
- `build_timestamp` is populated.

3. Spot check critical endpoint:
```bash
curl -fsS "https://<APP_HOST>/api/games/?limit=1"
```

## Rollback
1. Resolve and verify the rollback target:
```bash
poetry run python scripts/prepare_fly_rollback.py --env prod
```

2. Identify target release manually if needed:
```bash
fly releases -a <APP_NAME>
```

3. Roll back:
```bash
fly releases rollback <RELEASE_VERSION> -a <APP_NAME>
```

4. Re-run smoke checks:
- `/api`
- `/api/version`
- `/api/games/?limit=1`
- `poetry run python scripts/validate_prod_release.py`

5. If the rollback target predates the currently applied schema, assess whether a downgrade is actually required before attempting one. Default to fixing forward unless you have a tested downgrade path for the affected migrations.

## Release Mapping Record
For each production deploy, record:
1. Git tag or commit SHA
2. Fly release version
3. Deployment timestamp
4. Notes (schema/data migration impact, if any; include whether `alembic upgrade head` was run successfully)

The standard production validation flow now appends this record automatically to:
- `logs/deploy_traceability.jsonl`

## Common Inspection Queries
Use these for quick ad hoc operational checks.

Most recent suggestions in `dev`:
```bash
fly ssh console -a pax-tt-db-dev -C "psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c \"SELECT s.id, u.username, s.comment, s.timestamp FROM user_suggestions s JOIN users u ON u.id = s.user_id ORDER BY s.timestamp DESC LIMIT 20;\""
```
