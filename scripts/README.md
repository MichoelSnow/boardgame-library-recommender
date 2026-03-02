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
  - `docs/deploy_rollback_runbook.md`
- Environment strategy:
  - `docs/fly_environment_strategy.md`

## Operational Notes

- Fly machines may be auto-stopped when idle. If a script fails because no machine is running, use the wake commands in `docs/deploy_rollback_runbook.md`.
- The `.tmp/` directory is intentionally local-only and should not be committed.
