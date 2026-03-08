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
```
- Requirements:
  - `fly` CLI authenticated
  - `git` available

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

## `prepare_fly_rollback.py`
- What it does:
  - Resolves rollback target and prints exact Fly rollback command.
- When to use:
  - During prod validation and incident response prep.
- How to use:
```bash
poetry run python scripts/deploy/prepare_fly_rollback.py --env prod
poetry run python scripts/deploy/prepare_fly_rollback.py --env prod --target-release v41
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
