# Deploy Scripts

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
  - Captures prior machine autostop mode, then sets `autostop=off` before `start` to prevent Fly idle shutdown during import.
  - Starts a local watcher that auto-restores autostop mode after the tracked import PID exits.
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
  - Keep the local machine running while the import job is active so the watcher can restore autostop automatically.

## `fly_ingest_deploy.sh`
- What it does:
  - Deploys the dedicated ingest app (`bg-lib-ingest`) using `fly.ingest.toml`.
  - Injects `GIT_SHA` and `BUILD_TIMESTAMP` build args.
  - Stops the machine after deploy so ingest does not auto-run.
- When to use:
  - After one-time app + volume creation.
  - Initial setup of ingest worker app.
  - Updating ingest pipeline code in Fly image.
- How to use:
```bash
scripts/deploy/fly_ingest_deploy.sh
scripts/deploy/fly_ingest_deploy.sh fly.ingest.toml
```
- Requirements:
  - `fly` CLI authenticated
  - `git` available
  - optional `.env` value: `FLY_APP_NAME_INGEST`
  - writes timestamped local log: `logs/deploy/fly_ingest_deploy_<timestamp>.log`

## `fly_ingest_start.sh`
- What it does:
  - Starts the ingest machine manually.
  - Ingest process then runs end-to-end and exits.
- When to use:
  - Manual trigger for a fresh ingest run.
  - Manual resume trigger after failure.
- How to use:
```bash
scripts/deploy/fly_ingest_start.sh
```
- Requirements:
  - `fly` CLI authenticated
  - `jq` installed
  - optional `.env` value: `FLY_APP_NAME_INGEST`
  - writes timestamped local log: `logs/deploy/fly_ingest_start_<timestamp>.log`

One-time bootstrap before first use:
```bash
fly apps create "${FLY_APP_NAME_INGEST:-bg-lib-ingest}"
fly volumes create bg_lib_ingest_data \
  --app "${FLY_APP_NAME_INGEST:-bg-lib-ingest}" \
  --region iad \
  --size 20
```

## `fly_ingest_set_secrets.sh`
- What it does:
  - Loads `.env` and writes ingest secrets to Fly app (`bg-lib-ingest` by default).
  - Supports Brevo aliases for SMTP credentials.
- How to use:
```bash
scripts/deploy/fly_ingest_set_secrets.sh
```
- Required `.env` keys:
  - `BGG_TOKEN`
  - `BGG_RANKS_ZIP_URL`
  - `INGEST_NOTIFY_EMAIL_TO`
  - `INGEST_NOTIFY_EMAIL_FROM`
  - SMTP credentials via either:
    - `INGEST_NOTIFY_SMTP_USERNAME` + `INGEST_NOTIFY_SMTP_PASSWORD`
    - or Brevo aliases: `BREVO_SMTP_USERNAME`/`BREVO_SMTP_LOGIN` + `BREVO_SMTP_PASSWORD`/`BREVO_SMTP_KEY`
- Optional `.env` keys:
  - `FLY_APP_NAME_INGEST` (default `bg-lib-ingest`)
  - `INGEST_NOTIFY_SMTP_HOST` (default `smtp-relay.brevo.com`)
  - `INGEST_NOTIFY_SMTP_PORT` (default `587`)
  - `INGEST_NOTIFY_SMTP_STARTTLS` (default `true`)
  - writes timestamped local log: `logs/deploy/fly_ingest_set_secrets_<timestamp>.log`

## `fly_ingest_status.sh`
- What it does:
  - Shows ingest machine status.
  - If machine is started, prints current ingest run state JSON.
- How to use:
```bash
scripts/deploy/fly_ingest_status.sh
```
- Requirements:
  - `fly` CLI authenticated
  - optional `.env` values: `FLY_APP_NAME_INGEST`, `INGEST_RUN_STATE_PATH`
  - writes timestamped local log: `logs/deploy/fly_ingest_status_<timestamp>.log`

## `fly_ingest_list_artifacts.sh`
- What it does:
  - Lists available remote ingest output files for:
    - `/app/data/ingest/ranks`
    - `/app/data/ingest/game_data`
    - `/app/data/ingest/ratings`
  - Prints full remote path, size, and mtime for each matching artifact.
- When to use:
  - Immediately before download, to copy exact remote file paths.
- How to use:
```bash
scripts/deploy/fly_ingest_list_artifacts.sh
```
- Requirements:
  - `fly` CLI authenticated
  - optional `.env` value: `FLY_APP_NAME_INGEST`
  - writes timestamped local log: `logs/deploy/fly_ingest_list_artifacts_<timestamp>.log`

## `fly_ingest_download_artifact.sh`
- What it does:
  - Downloads large ingest artifacts from the ingest volume to local disk.
  - Supports resumable chunked download for multi-GB files.
  - Verifies local file against remote SHA-256 before finalizing output.
- When to use:
  - After remote ingest completes and you need DuckDB artifacts locally for transform/import.
  - After interrupted downloads; rerun with same arguments to resume.
- How to use:
```bash
# ranks CSV -> data/ingest/ranks (auto)
scripts/deploy/fly_ingest_download_artifact.sh \
  --remote-path /app/data/ingest/ranks/boardgame_ranks_<date>.csv

# game-data DuckDB -> data/ingest/game_data (auto)
scripts/deploy/fly_ingest_download_artifact.sh \
  --remote-path /app/data/ingest/game_data/boardgame_data_<timestamp>.duckdb \
  --chunk-mb 64

# ratings DuckDB -> data/ingest/ratings (auto)
scripts/deploy/fly_ingest_download_artifact.sh \
  --remote-path /app/data/ingest/ratings/boardgame_ratings_<timestamp>.duckdb \
  --chunk-mb 64
```
- Requirements:
  - `fly` CLI authenticated
  - `sha256sum` available locally
  - optional `.env` value: `FLY_APP_NAME_INGEST`
  - writes timestamped local log: `logs/deploy/fly_ingest_download_artifact_<timestamp>.log`
- Notes:
  - If `--output-dir` is omitted, destination is auto-selected from remote path:
    - `/app/data/ingest/ranks/*` -> `data/ingest/ranks`
    - `/app/data/ingest/game_data/*` -> `data/ingest/game_data`
    - `/app/data/ingest/ratings/*` -> `data/ingest/ratings`
  - Chunk cache is stored under the selected output directory as `.<filename>.parts/`.
  - Existing valid chunks are skipped, so reruns continue from last successful chunk.
  - Final output is promoted only if checksum matches remote file.
  - On successful verified download, `.parts` is removed by default.
  - Use `--keep-parts` to preserve chunk cache after success.

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
