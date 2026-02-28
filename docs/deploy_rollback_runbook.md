# Deploy and Rollback Runbook

## Purpose
- Standardize deployment and rollback for the Fly `dev` and `prod` apps.
- Ensure each release is traceable to git commit + Fly release.

## Deployment Policy
- Pull requests and feature branches run CI only.
- Pushes to `main` auto-deploy to the Fly `dev` app via GitHub Actions.
- Production deploys are manual promotions using the `Fly Deploy Prod` GitHub Actions workflow after `dev` smoke checks pass.

## Preconditions
- `flyctl` authenticated.
- Correct app selected (`dev` or `prod`).
- Required secrets are already set in Fly.

## Deploy to Dev
This is the normal path for `main` branch changes.

1. Merge to `main`.
2. GitHub Actions automatically runs `Fly Deploy Dev`.
3. Verify release version:
```bash
fly releases -a pax-tt-app-dev | head -n 5
```

## Promote to Prod (Default)
This is the canonical production deploy path.

1. Open GitHub Actions.
2. Select `Fly Deploy Prod`.
3. Click `Run workflow`.
4. Leave `git_ref` as `main` to deploy the current `main` branch, or enter a specific tag / commit SHA.
5. Wait for the workflow to complete successfully.
6. Verify release version:
```bash
fly releases -a pax-tt-app | head -n 5
```

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
1. Identify target release:
```bash
fly releases -a <APP_NAME>
```

2. Roll back:
```bash
fly releases rollback <RELEASE_VERSION> -a <APP_NAME>
```

3. Re-run smoke checks:
- `/api`
- `/api/version`
- `/api/games/?limit=1`

## Release Mapping Record
For each production deploy, record:
1. Git tag or commit SHA
2. Fly release version
3. Deployment timestamp
4. Notes (schema/data migration impact, if any)
