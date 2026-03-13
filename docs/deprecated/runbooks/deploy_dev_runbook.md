# Deploy to Dev

This is the normal path for `main` branch changes.

1. Merge to `main`.
2. GitHub Actions automatically runs `Fly Deploy Dev`.
3. Ensure required `dev` stack is started:
```bash
scripts/deploy/fly_stack.sh dev up
```
4. Run the database migration on the deployed dev app:
```bash
fly ssh console -a bg-lib-app-dev -C 'sh -lc "cd /app/backend && poetry run alembic upgrade head"'
```
5. Verify release version:
```bash
fly releases -a bg-lib-app-dev | head -n 5
```

## Validate Dev (After Every Successful Merge to `main`)
Run this after each successful merge to `main` once the `Fly Deploy Dev` workflow finishes.

1. Ensure required `dev` stack is started:
```bash
scripts/deploy/fly_stack.sh dev up
```
2. Run the database migration on the deployed dev app:
```bash
fly ssh console -a bg-lib-app-dev -C 'sh -lc "cd /app/backend && poetry run alembic upgrade head"'
```
3. Run the core validation script:
```bash
poetry run python scripts/validate/validate_dev_deploy.py
```
4. Confirm the database migration step completed successfully before treating the deploy as valid.
5. Confirm the script reports all of the following:
- `/api` responded with the expected message
- deployed `git_sha` matches `main`
- `build_timestamp` is populated
- Fly health checks are configured and passing
- unauthenticated access is rejected on protected endpoints
- if `SMOKE_TEST_USERNAME` and `SMOKE_TEST_PASSWORD_DEV` are set, the positive login flow succeeds
- recommendation artifact files exist in `/data`
- at least one matched artifact timestamp pair exists
- the recommendation endpoint returns non-empty results for the canonical smoke-test game (`224517`)
- latency thresholds pass for `/api`, `/api/version`, and the canonical recommendation endpoint
6. The script also records the validated SHA at `.tmp/validated_dev_sha.txt` for the prod promotion step.
7. Additional manual checks are only required when the merge affects the related area:
- if frontend behavior changed: open the dev site in a browser and verify the main UI loads plus the affected flow renders correctly
- if auth changed: manually test the full login, current-user flow, and password change path as applicable (the scripted auth smoke is intentionally lightweight)
- if deployment/config changed: review Fly logs and confirm startup logs show the app loaded a matched embeddings/mapping pair successfully
8. If validation passes and the change is intended for release, continue to production promotion.
9. If validation fails, fix forward on a new branch or roll back the dev deployment path as needed before promoting anything to prod.
