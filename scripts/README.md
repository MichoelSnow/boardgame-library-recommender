# Scripts

This directory contains operational and support scripts for local deployment,
validation, and data movement.

## Release and Deployment

### `fly_deploy.sh`

Purpose:
- Deploy the app to Fly with build metadata (`git_sha` and `build_timestamp`)

When to use:
- Local manual deploy to `dev`
- Local emergency fallback deploy to `prod` if the GitHub Actions workflow is unavailable

Usage:
```bash
scripts/fly_deploy.sh dev
scripts/fly_deploy.sh prod
```

Notes:
- This script reads the current checked-out commit SHA with `git rev-parse HEAD`
- It injects build metadata so `/api/version` can verify the deployed release

### `fly_stack.sh`

Purpose:
- Start/stop app+DB stacks safely with dependency-aware ordering.
- `up`: starts DB machine first, then app machine.
- `down`: stops app machine first, then DB machine.
- `status`: shows both machine states.

When to use:
- Before dev/prod validation when machines may be auto-stopped.
- For cost-control shutdown outside active test windows.

Usage:
```bash
scripts/fly_stack.sh dev up
scripts/fly_stack.sh dev down
scripts/fly_stack.sh dev status

scripts/fly_stack.sh prod up
scripts/fly_stack.sh prod down
scripts/fly_stack.sh prod status
```

Notes:
- Fly does not support native cross-app start dependencies.
- If a machine does not exist (for example after `fly scale count 0`), deploy that app to recreate it first.

## Deployment Validation

### `validate_dev_deploy.py`

Purpose:
- Run the standard post-merge validation flow for the `dev` Fly environment

When to use:
- After every successful merge to `main`, once the `Fly Deploy Dev` workflow completes

Usage:
```bash
poetry run python scripts/validate_dev_deploy.py
```

What it validates:
- `dev` `/api` responds correctly
- deployed `git_sha` matches `main`
- `build_timestamp` is populated
- Fly health checks are configured and passing
- unauthenticated access is rejected on protected endpoints
- if `SMOKE_TEST_USERNAME` and `SMOKE_TEST_PASSWORD_DEV` are set, the positive login flow succeeds
- recommendation artifact files exist
- at least one matched embeddings/mapping pair exists
- recommendation endpoint returns non-empty results for the canonical smoke-test game (`224517`)
- latency thresholds pass for `/api`, `/api/version`, and `/api/recommendations/224517`

Outputs:
- Writes the validated dev SHA to `.tmp/validated_dev_sha.txt`

### `validate_prod_release.py`

Purpose:
- Run the standard post-promotion validation flow for the `prod` Fly environment

When to use:
- After running the `Fly Deploy Prod` GitHub Actions workflow

Usage:
```bash
poetry run python scripts/validate_prod_release.py
```

Prerequisite:
- `.tmp/validated_dev_sha.txt` must already exist from a successful `validate_dev_deploy.py` run

What it validates:
- `prod` `/api` responds correctly
- deployed `git_sha` matches the previously validated dev SHA
- `build_timestamp` is populated
- Fly health checks are configured and passing
- unauthenticated access is rejected on protected endpoints
- if `SMOKE_TEST_USERNAME` and `SMOKE_TEST_PASSWORD_PROD` are set, the positive login flow succeeds
- recommendation artifact files exist
- at least one matched embeddings/mapping pair exists
- recommendation endpoint returns non-empty results for the canonical smoke-test game (`224517`)
- latency thresholds pass for `/api`, `/api/version`, and `/api/recommendations/224517`
- appends a production traceability record to `logs/deploy_traceability.jsonl`
- resolves and prints the exact rollback command for the current production release set

### `run_prod_health_alerts.py`

Purpose:
- Run periodic production P0 health checks and fail the workflow on unhealthy conditions.

When to use:
- Via scheduled GitHub Actions workflow (`.github/workflows/prod-health-alerts.yml`).
- Manually for dry-run verification before convention windows.

Usage:
```bash
poetry run python scripts/run_prod_health_alerts.py --env prod
poetry run python scripts/run_prod_health_alerts.py --env prod --dry-run
```

What it checks:
- App reachable and healthy (`GET /api`).
- Database-backed query path works (`GET /api/games/?limit=1...`).
- Recommendation subsystem availability (`GET /api/recommendations/status`).
- Convention mode gate:
  - exits without alerting unless `/api/version` reports `convention_mode=true`.

Alert classes (P0):
- `app_unreachable`
- `db_connectivity_failure`
- `recommendation_degraded`

Notification model:
- The script exits non-zero on P0 failures.
- GitHub Actions failure notifications are the alert delivery channel.
- No provider-specific email secrets are required.

### `validate_prod_alert_path.py`

Purpose:
- Smoke-validate the production alert path wiring before convention windows.

When to use:
- After changing alert workflow or alert script logic.
- Before enabling scheduled convention monitoring.

Usage:
```bash
poetry run python scripts/validate_prod_alert_path.py --env prod
poetry run python scripts/validate_prod_alert_path.py --env prod --skip-runtime
```

What it validates:
- workflow file exists and contains the expected 20-minute schedule
- workflow runs `scripts/run_prod_health_alerts.py --env prod`
- alert script includes convention-mode gating
- optional dry-run execution returns expected status semantics

### `validate_fly_release.py`

Purpose:
- Validate basic Fly release liveness and build metadata for `dev` or `prod`

When to use:
- Standalone diagnostics
- Lower-level check used by the wrapper validation scripts

Usage:
```bash
poetry run python scripts/validate_fly_release.py --env dev --expected-ref main
poetry run python scripts/validate_fly_release.py --env prod --expected-ref <commit-sha>
```

Optional:
```bash
poetry run python scripts/validate_fly_release.py --env dev --expected-ref main --write-sha-path .tmp/validated_dev_sha.txt
```

What it validates:
- `/api` responds with the expected message
- `/api/version` returns the expected `git_sha`
- `/api/version` includes a populated `build_timestamp`

### `validate_recommendation_artifacts.py`

Purpose:
- Validate recommendation artifact file presence and matched timestamp pairs on Fly

When to use:
- Standalone diagnostics
- Lower-level check used by the wrapper validation scripts

Usage:
```bash
poetry run python scripts/validate_recommendation_artifacts.py --env dev
poetry run python scripts/validate_recommendation_artifacts.py --env prod
```

What it validates:
- at least one `game_embeddings_*.npz` exists
- at least one `reverse_mappings_*.json` exists
- at least one matched timestamp pair exists
- reports the newest matched pair and a human-readable UTC timestamp

What it does not validate:
- whether startup logs show the matched pair was loaded
- whether a recommendation test case succeeds (that is covered by `validate_recommendation_endpoint.py`)

### `validate_recommendation_endpoint.py`

Purpose:
- Validate that the recommendation endpoint returns non-empty results for a known-good game

When to use:
- Standalone diagnostics
- Lower-level check used by the wrapper validation scripts

Usage:
```bash
poetry run python scripts/validate_recommendation_endpoint.py --env dev --game-id 224517
poetry run python scripts/validate_recommendation_endpoint.py --env prod --game-id 224517
```

What it validates:
- request succeeds
- response is a JSON list
- response is non-empty
- response headers do not report degraded recommendation mode

Default test case:
- game ID `224517`

### `validate_auth_flow.py`

Purpose:
- Validate the basic auth flow for `dev` or `prod`

When to use:
- Standalone diagnostics
- Lower-level check used by the wrapper validation scripts

Usage:
```bash
poetry run python scripts/validate_auth_flow.py --env local
poetry run python scripts/validate_auth_flow.py --env dev
poetry run python scripts/validate_auth_flow.py --env prod
```

Optional positive-login coverage:
```bash
poetry run python scripts/validate_auth_flow.py --env dev --username <user> --password <password>
```

What it validates:
- protected endpoints reject unauthenticated access with `401`
- if environment-specific smoke-test credentials are set in `.env` (or passed as args), login succeeds and `/api/users/me/` returns the expected user

Environment variable lookup order:
- shared username: `SMOKE_TEST_USERNAME`
- for `--env local`: `SMOKE_TEST_PASSWORD_LOCAL`
- for `--env dev`: `SMOKE_TEST_PASSWORD_DEV`
- for `--env prod`: `SMOKE_TEST_PASSWORD_PROD`
- fallback password: `SMOKE_TEST_PASSWORD`

### `validate_performance_gate.py`

Purpose:
- Enforce a lightweight latency gate before promotion

When to use:
- Standalone diagnostics
- Lower-level check used by the wrapper validation scripts

Usage:
```bash
poetry run python scripts/validate_performance_gate.py --env dev
poetry run python scripts/validate_performance_gate.py --env prod
```

Default thresholds:
- `/api` <= `1500ms`
- `/api/version` <= `1500ms`
- `/api/recommendations/224517?limit=5` <= `4000ms`

## Load Testing

### `load/k6_rehearsal.js`

Purpose:
- Run repeatable load tests against the rehearsal profile in `dev`.
- Exercise a read-heavy endpoint mix that matches expected convention behavior.

When to use:
- During Phase 4B rehearsal while `dev` is deployed with `fly.dev.rehearsal.toml`.
- Before adjusting worker count, machine memory, or latency/error budgets.

Current validated rehearsal runtime baseline:
- `APP_SERVER=gunicorn`
- `GUNICORN_WORKERS=3`
- `GUNICORN_CMD_ARGS=--timeout 90`
- `shared-cpu-4x`, `memory=2048`

Prerequisite:
- Install `k6` locally.

Usage (baseline):
```bash
k6 run \
  -e BASE_URL="https://pax-tt-app-dev.fly.dev" \
  -e VUS="10" \
  -e DURATION="2m" \
  scripts/load/k6_rehearsal.js
```

Usage (short-term rehearsal target):
```bash
k6 run \
  -e BASE_URL="https://pax-tt-app-dev.fly.dev" \
  -e VUS="100" \
  -e DURATION="15m" \
  scripts/load/k6_rehearsal.js
```

Usage (stress ramp):
```bash
k6 run \
  -e BASE_URL="https://pax-tt-app-dev.fly.dev" \
  -e VUS="200" \
  -e DURATION="10m" \
  -e THINK_TIME_SECONDS="0.1" \
  scripts/load/k6_rehearsal.js
```

Endpoint mix per virtual user iteration:
- `40%` `GET /api`
- `20%` `GET /api/version`
- `25%` `POST /api/recommendations` using a random `liked_games` subset:
  - subset size: random integer from `LIKED_MIN` to `LIKED_MAX` (defaults `1` to `50`)
  - source IDs: deduplicated random sample from `GAME_IDS` (CSV env var)
  - include at least 50 IDs in `GAME_IDS` if you want to fully exercise the default `1..50` range
- `15%` `GET /api/games/?skip=0&limit=20&sort_by=rank&pax_only=true`

Optional load-test env vars:
- `GAME_IDS` (CSV list of candidate IDs used for random recommendation subsets)
- `LIKED_MIN` (defaults to `1`)
- `LIKED_MAX` (defaults to `50`)
- `RECOMMENDATION_LIMIT` (defaults to `5`)
- `PAX_ONLY` (`true`/`false`, defaults to `true`)
- route weights (defaults preserve the mixed profile):
  - `WEIGHT_API` (default `0.40`)
  - `WEIGHT_VERSION` (default `0.20`)
  - `WEIGHT_RECOMMENDATIONS` (default `0.25`)
  - `WEIGHT_GAMES` (default `0.15`)

Usage (realistic wide-range recommendations):
```bash
k6 run \
  -e BASE_URL="https://pax-tt-app-dev.fly.dev" \
  -e GAME_IDS="<comma-separated IDs; include >=50 for full range>" \
  -e LIKED_MIN="1" \
  -e LIKED_MAX="50" \
  -e VUS="10" \
  -e DURATION="5m" \
  -e THINK_TIME_SECONDS="2.0" \
  scripts/load/k6_rehearsal.js
```

Usage (stress heavier recommendation sets):
```bash
k6 run \
  -e BASE_URL="https://pax-tt-app-dev.fly.dev" \
  -e GAME_IDS="<comma-separated IDs; include >=50 for full range>" \
  -e LIKED_MIN="20" \
  -e LIKED_MAX="50" \
  -e VUS="10" \
  -e DURATION="5m" \
  -e THINK_TIME_SECONDS="2.0" \
  scripts/load/k6_rehearsal.js
```

Usage (recommendations-only isolation):
```bash
k6 run \
  -e BASE_URL="https://pax-tt-app-dev.fly.dev" \
  -e GAME_IDS="<comma-separated IDs; include >=50 for full range>" \
  -e LIKED_MIN="1" \
  -e LIKED_MAX="50" \
  -e VUS="10" \
  -e DURATION="3m" \
  -e THINK_TIME_SECONDS="2.0" \
  -e WEIGHT_API="0" \
  -e WEIGHT_VERSION="0" \
  -e WEIGHT_RECOMMENDATIONS="1" \
  -e WEIGHT_GAMES="0" \
  scripts/load/k6_rehearsal.js
```

Usage (games-only isolation):
```bash
k6 run \
  -e BASE_URL="https://pax-tt-app-dev.fly.dev" \
  -e VUS="10" \
  -e DURATION="3m" \
  -e THINK_TIME_SECONDS="2.0" \
  -e WEIGHT_API="0" \
  -e WEIGHT_VERSION="0" \
  -e WEIGHT_RECOMMENDATIONS="0" \
  -e WEIGHT_GAMES="1" \
  scripts/load/k6_rehearsal.js
```

Built-in thresholds:
- global request failure rate `< 2%`
- global p95 request latency `< 2500ms`
- recommendation p95 latency `< 4000ms`
- recommendation failure rate `< 2%`
- games-list p95 latency `< 2500ms`
- games-list failure rate `< 2%`

Recorded Phase 4B baseline results (2026-03-06):
- mixed profile, `VUS=10`, `DURATION=3m`, `THINK_TIME_SECONDS=2.0`:
  - `http_req_failed=0.00%`
  - `http_req_duration p95=165.81ms`
  - `games_duration p95=213.29ms`
  - `recommendation_duration p95=198.45ms`
- mixed profile, `VUS=30`, `DURATION=3m`, `THINK_TIME_SECONDS=2.0`:
  - `http_req_failed=0.00%`
  - `http_req_duration p95=181.29ms`
  - `games_duration p95=202.76ms`
  - `recommendation_duration p95=284.80ms`

### `benchmark_recommendation_size.py`

Purpose:
- Isolate how recommendation-request latency changes as liked-game list size grows.
- Run fixed-size, sequential recommendation calls (`POST /api/recommendations`) to separate payload-cost effects from high-concurrency overload effects.

When to use:
- During recommendation performance diagnosis.
- Before/after backend optimization to compare size-impact.

Usage:
```bash
poetry run python scripts/benchmark_recommendation_size.py \
  --env dev \
  --game-ids "224517,161936,342942,174430,316554,233078,167791,115746,187645,397598,162886,291457,220308,12333,182028,84876,193738,246900,169786,28720,173346,295770,167355,177736,266507,124361,312484,341169,205637,421006,237182,338960,192135,373106,418059,120677,266192,164928,96848,251247,199792,324856,183394,321608,366013,285774,521,284378,175914,247763,256960,3076,253344,295947,184267,102794,314040,383179,185343,170216,31260,251661,161533,255984,365717,231733,182874,221107,414317,205059,126163,2651,390092,244521,216132,266810,35677,125153,164153,276025,124742,371942,200680,209010,240980,284083,55690,380607,28143,332772,230802,157354,322289,201808,366161,159675,72125,191189,93,291453" \
  --sizes "1,5,10,20,35,50" \
  --iterations 20 \
  --limit 5 \
  --pax-only true
```

Output:
- Logs one summary line per liked-game size:
  - success count
  - error rate
  - p50/p95/max latency
  - HTTP status distribution
- Prints JSON summary for easier copy/paste into docs.

### `validate_fly_health_checks.py`

Purpose:
- Confirm Fly platform health checks are configured and passing

When to use:
- Standalone diagnostics
- Lower-level check used by the wrapper validation scripts

Usage:
```bash
poetry run python scripts/validate_fly_health_checks.py --env dev
poetry run python scripts/validate_fly_health_checks.py --env prod
```

### `record_deploy_traceability.py`

Purpose:
- Append a local deploy traceability record for a promotion event

When to use:
- Automatically during `validate_prod_release.py`
- Standalone if you need to record a promotion event manually

Usage:
```bash
poetry run python scripts/record_deploy_traceability.py --env prod --expected-sha-path .tmp/validated_dev_sha.txt --marker prod-promotion
```

Convention profile switch markers:
```bash
poetry run python scripts/record_deploy_traceability.py --env prod --marker convention-profile-enable
poetry run python scripts/record_deploy_traceability.py --env prod --marker convention-profile-disable
```

Output:
- Appends one JSON line to `logs/deploy_traceability.jsonl`

### `create_smoke_test_user.py`

Purpose:
- Create the shared smoke-test user in `local`, `dev`, or `prod` using the app API

When to use:
- One-time setup for auth smoke testing
- Recreate the smoke-test user if it is removed or credentials change

Usage:
```bash
poetry run python scripts/create_smoke_test_user.py --env local
poetry run python scripts/create_smoke_test_user.py --env dev
poetry run python scripts/create_smoke_test_user.py --env prod
```

### `fly_postgres_backup.py`

Purpose:
- Create a logical SQL backup from the self-managed Fly Postgres app for `dev` or `prod`

When to use:
- Before risky database changes
- Before the production Postgres cutover
- As part of the pre-convention backup workflow

Usage:
```bash
poetry run python scripts/fly_postgres_backup.py --env dev
poetry run python scripts/fly_postgres_backup.py --env prod --output /tmp/pax-tt-prod-before-cutover.sql
```

What it does:
- Runs `pg_dump` over `fly ssh console`
- Writes the resulting SQL dump to a local file
- Fails if the resulting backup file is empty

### `fly_postgres_restore.py`

Purpose:
- Restore a Fly Postgres SQL dump into a disposable test database on the `dev` or `prod` DB app

When to use:
- To validate the restore procedure before convention launch
- To prove a generated SQL dump can be loaded successfully

Usage:
```bash
poetry run python scripts/fly_postgres_restore.py --env dev --input /tmp/pax-tt-dev-postgres-backup-20260304T012020Z.sql
poetry run python scripts/fly_postgres_restore.py --env prod --input /tmp/pax-tt-prod-before-cutover.sql --restore-db pax_tt_recommender_restore_test
```

What it does:
- Drops and recreates a disposable restore database
- Pipes the local SQL dump into `psql` over `fly ssh console`
- Verifies the restored database has public tables

Required environment variables:
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `SMOKE_TEST_USERNAME`
- environment-specific password:
  - `SMOKE_TEST_PASSWORD_LOCAL`
  - `SMOKE_TEST_PASSWORD_DEV`
  - `SMOKE_TEST_PASSWORD_PROD`

### `prepare_fly_rollback.py`

Purpose:
- Resolve the safest rollback target and print the exact Fly rollback command

When to use:
- Automatically during `validate_prod_release.py`
- Before any manual rollback

Usage:
```bash
poetry run python scripts/prepare_fly_rollback.py --env prod
poetry run python scripts/prepare_fly_rollback.py --env prod --target-release v34
```

## Legacy / Utility Scripts

### `build-for-production.sh`

Purpose:
- Legacy helper script from earlier workflow

Status:
- Review before use; current release workflow is centered on Fly deploy workflows and `scripts/fly_deploy.sh`

### `upload_files.sh`

Purpose:
- Utility script for manual file upload workflows

Status:
- Use only if you explicitly need that legacy/manual flow

### `upload_to_fly_volume.sh`

Purpose:
- Utility script for manually copying files into a Fly volume

Status:
- Use only when performing manual volume maintenance or recovery tasks

## Related Documentation

- Main operational runbook:
  - `docs/runbooks/deploy_rollback_runbook.md`
- Environment strategy:
  - `docs/architecture/fly_environment_strategy.md`

## Operational Notes

- Fly machines may be auto-stopped when idle. If a script fails because no machine is running, use the wake commands in `docs/runbooks/deploy_rollback_runbook.md`.
- The `.tmp/` directory is intentionally local-only and should not be committed.
