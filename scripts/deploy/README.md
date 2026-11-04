# Deploy Scripts

The dedicated ingest worker is operated through
[`scripts/ingest/fly_ingest.sh`](../ingest/README.md). The old ingest
start/status entry points have been removed; do not invoke individual deploy
helpers directly for normal ingest operations.

## `fly_deploy.sh`
- What it does:
  - Deploys `dev` or `prod` app with `GIT_SHA` and `BUILD_TIMESTAMP` build args.
- When to use:
  - Local fallback deploys when not using GitHub Actions deployment flow.
- How to use:
```bash
scripts/deploy/fly_deploy.sh dev
scripts/deploy/fly_deploy.sh prod
scripts/deploy/fly_deploy.sh prod --config fly.convention.toml
scripts/deploy/fly_deploy.sh dev --config fly.convention.dev.toml
```
- Requirements:
  - `fly` CLI authenticated
  - `git` available
  - `.env` with `FLY_APP_NAME_DEV` / `FLY_APP_NAME_PROD`

## `fly_stack.sh`
- What it does:
  - Orchestrates app+DB machine lifecycle with safe ordering.
  - `up`: DB -> app
  - `down`: app -> DB
  - `status`: show both
- When to use:
  - Before/after validations in auto-stop environments.
- How to use:
```bash
scripts/deploy/fly_stack.sh dev up
scripts/deploy/fly_stack.sh dev down
scripts/deploy/fly_stack.sh dev status
```
- Requirements:
  - `fly` CLI authenticated
  - `jq` installed
  - `.env` with `FLY_APP_NAME_*` and `FLY_DB_APP_NAME_*`

## `fly_import_data_job.sh`
- What it does:
  - Runs `alembic upgrade head` + `app/import_data.py --delete-existing` as a detached remote job.
  - Persists logs under `/data/logs/import_data/` on the Fly app volume.
  - Streams the same output to Fly Machine Logs/Errors.
  - Requires a resolvable machine ID and an existing `autostop=stop` policy before starting.
  - Temporarily sets `autostop=off`, starts the machine if needed, and waits for it to reach `started` before opening SSH.
  - Starts a local watcher that restores `autostop=stop` after the tracked import PID exits, on watcher interruption, or when its four-hour safety timeout is reached.
  - `stop` still force-restores `autostop=stop` for manual cleanup/override.
  - `status` is read-only (reports PID/log without changing machine config).
  - `status` also prints resolved machine id and service policy (`autostop`, `autostart`, `min_machines_running`).
  - `status` also prints local watcher status.
  - Supports `start`, `status`, `tail`, `log`, and `stop` actions.
  - Local watcher artifacts are written under `.tmp/import_data_watchers/`.
- When to use:
  - Long-running imports where SSH session drops are a risk.
- How to use:
```bash
scripts/deploy/fly_import_data_job.sh dev start
scripts/deploy/fly_import_data_job.sh dev status
scripts/deploy/fly_import_data_job.sh dev tail
scripts/deploy/fly_import_data_job.sh dev log
scripts/deploy/fly_import_data_job.sh dev stop
```
- Requirements:
  - `fly` CLI authenticated
  - `.env` with `FLY_APP_NAME_DEV` / `FLY_APP_NAME_PROD`
  - Keep the local machine running while the import job is active so the watcher can restore autostop promptly; timeout restoration is a safety net.

## Dedicated ingest worker

Use [`scripts/ingest/fly_ingest.sh`](../ingest/README.md) for all ingest
operations. It provides the canonical commands for deployment, secret sync,
machine lifecycle, fresh/resumed/ratings-only runs, logs, and artifact export.

The lower-level `fly_ingest_*.sh` files in this directory are implementation
helpers used by the dispatcher and are not operator-facing commands.

## `generate_env_secrets.sh`
- What it does:
  - Generates strong random secrets and writes deployment/local env keys to `.env` (or provided env-file path).
  - Sets non-secret deployment defaults (DB/user/ports/Fly app-name scaffolding) with consistent naming.
  - Replaces managed keys atomically to avoid duplicate stale entries.
  - Rewrites deploy target app names in:
    - `fly.dev.toml`
    - `fly.toml`
    - `fly.db.dev.toml`
    - `fly.db.prod.toml`
    - `.github/workflows/fly-deploy.yml`
    - `.github/workflows/fly-deploy-prod.yml`
  - Enforces `chmod 600` on the target env file.
- When to use:
  - First-time setup before local/Fly deployment.
  - Credential rotation for local deployment env files.
- How to use:
```bash
bash scripts/deploy/generate_env_secrets.sh .env
```
- Optional custom Fly app-name prefix:
```bash
bash scripts/deploy/generate_env_secrets.sh .env my-unique-prefix
```
or:
```bash
APP_PREFIX=my-unique-prefix bash scripts/deploy/generate_env_secrets.sh .env
```

## `prepare_fly_rollback.py`
- What it does:
  - Prints recent deployments (version, time, ID, status, user, image token).
  - Resolves rollback target and prints exact rollback command.
  - Uses rollback target image and emits a `fly deploy --image ...` command compatible with current `flyctl`.
- When to use:
  - During prod validation and incident response prep.
- How to use:
```bash
poetry run python scripts/deploy/prepare_fly_rollback.py --env prod
poetry run python scripts/deploy/prepare_fly_rollback.py --env prod --target-release v41
poetry run python scripts/deploy/prepare_fly_rollback.py --env prod --limit 10
poetry run python scripts/deploy/prepare_fly_rollback.py --env dev --config-file fly.convention.dev.toml
```

## `record_deploy_traceability.py`
- What it does:
  - Appends deploy metadata (`sha`, `build_timestamp`, Fly release) to `logs/deploy_traceability.jsonl`.
- When to use:
  - After promotions and profile-switch markers.
- How to use:
```bash
poetry run python scripts/deploy/record_deploy_traceability.py \
  --env prod \
  --marker prod-promotion \
  --expected-sha-path .tmp/validated_dev_sha.txt
```
