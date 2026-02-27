# Deploy and Rollback Runbook

## Purpose
- Standardize deployment and rollback for the Fly `dev` and `prod` apps.
- Ensure each release is traceable to git commit + Fly release.

## Preconditions
- `flyctl` authenticated.
- Correct app selected (`dev` or `prod`).
- Required secrets are already set in Fly.

## Deploy (with build metadata)
1. Get metadata values:
```bash
GIT_SHA=$(git rev-parse HEAD)
BUILD_TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

2. Deploy:
```bash
fly deploy -a <APP_NAME> \
  --build-arg GIT_SHA="$GIT_SHA" \
  --build-arg BUILD_TIMESTAMP="$BUILD_TIMESTAMP"
```

3. Verify release version:
```bash
fly releases -a <APP_NAME> | head -n 5
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
