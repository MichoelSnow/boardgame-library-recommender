# Promote to Prod

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
scripts/deploy/fly_stack.sh prod up
```
9. Run the database migration on the deployed prod app:
```bash
fly ssh console -a bg-lib-app -C 'sh -lc "cd /app/backend && poetry run alembic upgrade head"'
```
10. Verify the database migration completed successfully before treating the production deploy as valid.
11. Verify the new Fly release exists:
```bash
fly releases -a bg-lib-app | head -n 5
```
12. Run the core production validation script:
```bash
poetry run python scripts/validate/validate_prod_release.py
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
- if frontend behavior changed: open `https://bg-lib-app.fly.dev` and verify the main UI plus the changed user flow render correctly
- if auth changed: manually test the full login, current-user flow, and password change path as applicable in `prod` (the scripted auth smoke is intentionally lightweight)
- if deployment/config changed: review `fly logs -a bg-lib-app` and confirm startup logs show the app loaded a matched embeddings/mapping pair successfully
15. If any production validation step fails, stop and either fix forward immediately or run rollback steps.

## Periodic Prod Alerting
- Scheduled production P0 health alerting is implemented via:
  - `.github/workflows/prod-health-alerts.yml`
  - `scripts/alerts/run_prod_health_alerts.py`
- Workflow cadence:
  - every 20 minutes
  - plus manual trigger (`workflow_dispatch`)
- Convention-mode gate:
  - workflow exits cleanly when `CONVENTION_MODE` is not active
- Default notification path:
  - GitHub Actions failure notifications (no extra services required)
- Smoke-validate alert path wiring before enabling schedule:
```bash
poetry run python scripts/validate/validate_prod_alert_path.py --env prod --skip-runtime
```

## Local Emergency Fallback Deploy
Use this only if the GitHub Actions workflow is unavailable and you need to deploy manually.

```bash
scripts/deploy/fly_deploy.sh prod
```

For a local manual deploy to dev:

```bash
scripts/deploy/fly_deploy.sh dev
```

After either manual deploy, run the required migration before validation:

```bash
fly ssh console -a bg-lib-app-dev -C 'sh -lc "cd /app/backend && poetry run alembic upgrade head"'
fly ssh console -a bg-lib-app -C 'sh -lc "cd /app/backend && poetry run alembic upgrade head"'
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
