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
- Local development also requires `.env` with `SECRET_KEY` (minimum 32 characters) before the backend will start.
- Optional but recommended for full auth smoke coverage: set `SMOKE_TEST_USERNAME` and `SMOKE_TEST_PASSWORD` in local `.env`.

## Quick Wake Commands
Fly machines may be stopped when idle because `auto_stop_machines = 'stop'`.
If a validation command fails due to no started VM or returns a startup-time `503`, start the machine first:

```bash
fly status -a pax-tt-app-dev
fly machine start <DEV_MACHINE_ID> -a pax-tt-app-dev
```

For production:

```bash
fly status -a pax-tt-app
fly machine start <PROD_MACHINE_ID> -a pax-tt-app
```

## Deploy to Dev
This is the normal path for `main` branch changes.

1. Merge to `main`.
2. GitHub Actions automatically runs `Fly Deploy Dev`.
3. Verify release version:
```bash
fly releases -a pax-tt-app-dev | head -n 5
```

## Validate Dev (After Every Successful Merge to `main`)
Run this after each successful merge to `main` once the `Fly Deploy Dev` workflow finishes.

1. Run the core validation script:
```bash
python scripts/validate_dev_deploy.py
```
2. Confirm the script reports all of the following:
- `/api` responded with the expected message
- deployed `git_sha` matches `main`
- `build_timestamp` is populated
- Fly health checks are configured and passing
- unauthenticated access is rejected on protected endpoints
- if `SMOKE_TEST_USERNAME` and `SMOKE_TEST_PASSWORD` are set, the positive login flow succeeds
- recommendation artifact files exist in `/data`
- at least one matched artifact timestamp pair exists
- the recommendation endpoint returns non-empty results for the canonical smoke-test game (`224517`)
- latency thresholds pass for `/api`, `/api/version`, and the canonical recommendation endpoint
3. The script also records the validated SHA at `.tmp/validated_dev_sha.txt` for the prod promotion step.
4. Additional manual checks are only required when the merge affects the related area:
- if frontend behavior changed: open the dev site in a browser and verify the main UI loads plus the affected flow renders correctly
- if auth changed: manually test the full login, current-user flow, and password change path as applicable (the scripted auth smoke is intentionally lightweight)
- if deployment/config changed: review Fly logs and confirm startup logs show the app loaded a matched embeddings/mapping pair successfully
5. If validation passes and the change is intended for release, continue to **Promote to Prod (Default)** below using the validated SHA.
6. If validation fails, fix forward on a new branch or roll back the dev deployment path as needed before promoting anything to prod.

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
8. Verify the new Fly release exists:
```bash
fly releases -a pax-tt-app | head -n 5
```
9. Run the core production validation script:
```bash
python scripts/validate_prod_release.py
```
10. Confirm the script reports all of the following:
- `/api` responded with the expected message
- deployed `git_sha` matches the validated SHA from `.tmp/validated_dev_sha.txt`
- `build_timestamp` is populated
- Fly health checks are configured and passing
- unauthenticated access is rejected on protected endpoints
- if `SMOKE_TEST_USERNAME` and `SMOKE_TEST_PASSWORD` are set, the positive login flow succeeds
- recommendation artifact files exist in `/data`
- at least one matched artifact timestamp pair exists
- the recommendation endpoint returns non-empty results for the canonical smoke-test game (`224517`)
- latency thresholds pass for `/api`, `/api/version`, and the canonical recommendation endpoint
- deploy traceability is recorded locally in `logs/deploy_traceability.jsonl`
- a valid rollback target is resolved and the exact rollback command is printed
11. Additional manual checks are only required when the release affects the related area:
- if frontend behavior changed: open `https://pax-tt-app.fly.dev` and verify the main UI plus the changed user flow render correctly
- if auth changed: manually test the full login, current-user flow, and password change path as applicable in `prod` (the scripted auth smoke is intentionally lightweight)
- if deployment/config changed: review `fly logs -a pax-tt-app` and confirm startup logs show the app loaded a matched embeddings/mapping pair successfully
12. If any production validation step fails, stop and either fix forward immediately or run the rollback steps below.

## Local Emergency Fallback Deploy
Use this only if the GitHub Actions workflow is unavailable and you need to deploy manually.

```bash
scripts/fly_deploy.sh prod
```

For a local manual deploy to dev:

```bash
scripts/fly_deploy.sh dev
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
python scripts/prepare_fly_rollback.py --env prod
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
- `python scripts/validate_prod_release.py`

## Release Mapping Record
For each production deploy, record:
1. Git tag or commit SHA
2. Fly release version
3. Deployment timestamp
4. Notes (schema/data migration impact, if any)

The standard production validation flow now appends this record automatically to:
- `logs/deploy_traceability.jsonl`
