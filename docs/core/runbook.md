# Runbook

## Deployment Policy
- CI runs on PRs and branch pushes.
- `main` auto-deploys to Fly `dev`.
- `prod` deploy is a manual promotion after `dev` validation passes.

## Preconditions
- `flyctl` authenticated.
- Required secrets configured for target app.
- Run DB migration on deploy before considering release valid.
- Load `.env` so `FLY_*` app-name variables are available for commands that reference them.

## Standard Dev Flow After Merge to Main
1. Ensure stack is running: 
```bash
scripts/deploy/fly_stack.sh dev up
```
2. Migrate:
```bash
fly ssh console -a "${FLY_APP_NAME_DEV}" -C 'sh -lc "cd /app/backend && poetry run alembic upgrade head"'
```
3. Validate:
```bash
poetry run python scripts/validate/validate_dev_deploy.py
```

## Deploy and Validate Without Merging from Main
1. Ensure stack is running: 
```bash
scripts/deploy/fly_stack.sh dev up
```
2. Deploy (only when testing a local branch/ref in dev): 
```bash
scripts/deploy/fly_deploy.sh dev
```
3. Migrate:
```bash
fly ssh console -a "${FLY_APP_NAME_DEV}" -C 'sh -lc "cd /app/backend && poetry run alembic upgrade head"'
```
4. Validate:
```bash
poetry run python scripts/validate/validate_fly_release.py --env dev --expected-ref HEAD
poetry run python scripts/validate/validate_fly_health_checks.py --env dev
poetry run python scripts/validate/validate_auth_flow.py --env dev
poetry run python scripts/validate/validate_recommendation_endpoint.py --env dev --game-id 224517
poetry run python scripts/validate/validate_performance_gate.py --env dev
```

## Standard Prod Promotion Flow
1. Confirm validated SHA from `.tmp/validated_dev_sha.txt`.
2. Run `Fly Deploy Prod` workflow with that exact SHA.
3. Ensure stack is running: 
```bash
scripts/deploy/fly_stack.sh prod up
```
4. Migrate:
```bash
fly ssh console -a "${FLY_APP_NAME_PROD}" -C 'sh -lc "cd /app/backend && poetry run alembic upgrade head"'
```
5. Validate:
```bash
poetry run python scripts/validate/validate_prod_release.py
```

## Rollback
1. Resolve rollback target:
```bash
poetry run python scripts/deploy/prepare_fly_rollback.py --env prod
```
2. Roll back release:
```bash
fly releases rollback <RELEASE_VERSION> -a "${FLY_APP_NAME_PROD}"
```
3. Re-run smoke/validation checks.

## Release Traceability
Record per prod promotion:
- Fly release version
- migration notes

### Versioning Policy
- Do not bump the app version on every commit or every `dev` deploy.
- Use `git_sha` and `build_timestamp` for commit-level traceability on `dev`.
- Bump the app version only for intentional `prod` releases.
- Every new `prod` deploy should increase the release version by at least one increment.
- The canonical app version source is `pyproject.toml`.

### How To Bump
1. Merge this feature branch (no version bump here).
2. Validate on dev.
3. Create a small release-version branch that only bumps `pyproject.toml`.
    - set the commit message/PR title to begin with `chore(release):` in order to not trigger the pr-agent
4. Merge that bump branch.
5. Validate dev on that exact SHA.
6. Promote that exact SHA to prod.
7. Tag/release that same prod-promoted SHA.

```bash
git tag -a prod-v0.X.Y -m "Release v0.X.Y"
git push origin prod-v0.X.Y
```

`logs/deploy_traceability.jsonl` is the canonical local trace log.

## Incident Fallback
If GitHub workflow is unavailable:
- `scripts/deploy/fly_deploy.sh prod`
- run migration and prod validation immediately after.

## Incident Triage Steps
1. Confirm app/machine status (`fly machines list` for app + db).
2. Check recent releases and identify latest known-good release.
3. Inspect recent logs for startup errors, DB connectivity issues, or repeated 5xx.
4. Run targeted validation checks (`validate_fly_release`, `validate_auth_flow`, recommendation health).
5. Decide fix-forward vs rollback; default to fix-forward unless rollback path is clearly safer.
6. Record incident actions and outcome in deploy/ops notes.

## Fly Stack Safety Notes
- Use `scripts/deploy/fly_stack.sh <env> up|down|status` for normal lifecycle operations.
- Avoid `fly scale count 0` as a routine stop/start mechanism; it can force machine/volume recreation work.

## Reference
- Fast command index: [docs/core/command_reference.md](/docs/core/command_reference.md)
- Convention-specific operations: [docs/core/convention_ops.md](/docs/core/convention_ops.md)
