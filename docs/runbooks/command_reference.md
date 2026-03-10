# Command Reference

Use this file for common operational commands that are easy to forget.

## 0. Environment Bootstrap

Load environment variables from local `.env`:

```bash
set -a
source .env
set +a
```

## 1. Local Development

Backend (local dev):

```bash
poetry run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend (local dev):

```bash
cd frontend
npm start
```

Apply local migrations:

```bash
poetry run alembic upgrade head
```

## 2. Fly Stack Lifecycle

Bring full stack up/down/status:

```bash
scripts/deploy/fly_stack.sh dev up
scripts/deploy/fly_stack.sh dev down
scripts/deploy/fly_stack.sh dev status

scripts/deploy/fly_stack.sh prod up
scripts/deploy/fly_stack.sh prod down
scripts/deploy/fly_stack.sh prod status
```

## 3. Deploy and Promote

Deploy app with SHA and build timestamp:

```bash
scripts/deploy/fly_deploy.sh dev
scripts/deploy/fly_deploy.sh prod
```

Run migrations inside Fly app machine:

```bash
fly ssh console -a pax-tt-app-dev -C 'sh -lc "cd /app/backend && poetry run alembic upgrade head"'
fly ssh console -a pax-tt-app -C 'sh -lc "cd /app/backend && poetry run alembic upgrade head"'
```

## 4. Validation

Dev full validation:

```bash
poetry run python scripts/validate/validate_dev_deploy.py
```

Prod full validation:

```bash
poetry run python scripts/validate/validate_prod_release.py
```

Targeted validation set (dev):

```bash
poetry run python scripts/validate/validate_fly_release.py --env dev --expected-ref HEAD
poetry run python scripts/validate/validate_fly_health_checks.py --env dev
poetry run python scripts/validate/validate_auth_flow.py --env dev
poetry run python scripts/validate/validate_recommendation_endpoint.py --env dev --game-id 224517
poetry run python scripts/validate/validate_performance_gate.py --env dev
```

## 5. DB Inspection and Suggestions

Check runtime DB URL locally:

```bash
poetry run python -c "from backend.app.db_config import get_database_url; print(get_database_url())"
```

Most recent suggestions in dev:

```bash
fly ssh console -a pax-tt-db-dev -C 'sh -lc "psql -U pax_tt_app -d pax_tt_recommender -c \"SELECT id, user_id, comment, timestamp FROM user_suggestions ORDER BY timestamp DESC LIMIT 20;\""'
```

Most recent suggestions in prod:

```bash
fly ssh console -a pax-tt-db-prod -C 'sh -lc "psql -U pax_tt_app -d pax_tt_recommender -c \"SELECT id, user_id, comment, timestamp FROM user_suggestions ORDER BY timestamp DESC LIMIT 20;\""'
```

Most recent suggestions (local SQLite):

```bash
sqlite3 backend/database/boardgames.db "SELECT id, user_id, comment, timestamp FROM user_suggestions ORDER BY timestamp DESC LIMIT 20;"
```

Most recent suggestions (local Postgres):

```bash
psql "$DATABASE_URL" -c "SELECT id, user_id, comment, timestamp FROM user_suggestions ORDER BY timestamp DESC LIMIT 20;"
```

## 6. DB Backup and Restore

Backup:

```bash
poetry run python scripts/db/fly_postgres_backup.py --env dev
poetry run python scripts/db/fly_postgres_backup.py --env prod --output /tmp/pax-tt-prod-backup.sql
```

Restore:

```bash
poetry run python scripts/db/fly_postgres_restore.py --env dev --input /tmp/pax-tt-dev-backup.sql
poetry run python scripts/db/fly_postgres_restore.py --env prod --input /tmp/pax-tt-prod-backup.sql --restore-db pax_tt_recommender_restore_test
```

## 7. Incident Triage

Machine state:

```bash
fly machines list -a pax-tt-app-dev
fly machines list -a pax-tt-db-dev
fly machines list -a pax-tt-app
fly machines list -a pax-tt-db-prod
```

App logs:

```bash
fly logs -a pax-tt-app-dev | tee -a logs/pax-tt-app-dev.fly.log
fly logs -a pax-tt-app | tee -a logs/pax-tt-app.fly.log
```

Common error patterns:

```bash
fly logs -a pax-tt-app-dev | rg -n "ERROR|CRITICAL|WORKER TIMEOUT|Out of memory|Killed process|Traceback"
fly logs -a pax-tt-app | rg -n "ERROR|CRITICAL|WORKER TIMEOUT|Out of memory|Killed process|Traceback"
```

## 8. Alerting and Workflow Toggles

Run prod health alert job manually:

```bash
poetry run python scripts/alerts/run_prod_health_alerts.py --env prod
poetry run python scripts/alerts/run_prod_health_alerts.py --env prod --dry-run
```

Validate alert path:

```bash
poetry run python scripts/validate/validate_prod_alert_path.py --env prod --skip-runtime
poetry run python scripts/validate/validate_prod_alert_path.py --env prod
```

Enable/disable scheduled prod alerts workflow:

```bash
gh workflow enable prod-health-alerts.yml
gh workflow disable prod-health-alerts.yml
```

## 9. Release and Rollback Helpers

Record deploy traceability:

```bash
poetry run python scripts/deploy/record_deploy_traceability.py --env prod --marker prod-promotion --expected-sha-path .tmp/validated_dev_sha.txt
```

Prepare rollback target:

```bash
poetry run python scripts/deploy/prepare_fly_rollback.py --env prod
```

Tag release:

Flow:
1. Merge this feature branch (no version bump here).
2. Validate on dev.
3. Create a small release-version branch that only bumps `pyproject.toml`.
4. Merge that bump branch.
5. Validate dev on that exact SHA.
6. Promote that exact SHA to prod.
7. Tag/release that same prod-promoted SHA.

That keeps versioning tied to intentional prod releases, not intermediate implementation commits.

```bash
git tag -a prod-v0.X.Y -m "Release v0.X.Y"
git push origin prod-v0.X.Y
```

## 10. Load and Performance

Recommendation size benchmark:

```bash
poetry run python scripts/perf/benchmark_recommendation_size.py --env dev --game-ids "<csv>" --sizes "1,5,10,20,35,50" --iterations 20 --limit 5 --pax-only true
```

k6 rehearsal:

```bash
k6 run \
  -e BASE_URL="https://pax-tt-app-dev.fly.dev" \
  -e GAME_IDS="<csv>" \
  -e VUS="10" \
  -e DURATION="3m" \
  -e THINK_TIME_SECONDS="2.0" \
  scripts/load/k6_rehearsal.js
```
## 11. Fly Image Seed (Primary)

Seed all qualified images directly from BGG to Fly dev volume:

```bash
fly ssh console -a pax-tt-app-dev -C 'sh -lc "cd /app && poetry run python -m data_pipeline.src.assets.sync_fly_images --scope all-qualified --max-rank 10000"'
```

Dry run candidate count:

```bash
fly ssh console -a pax-tt-app-dev -C 'sh -lc "cd /app && poetry run python -m data_pipeline.src.assets.sync_fly_images --scope all-qualified --max-rank 10000 --dry-run"'
```

PAX-only seed:
```bash
fly ssh console -a pax-tt-app-dev -C 'sh -lc "cd /app && poetry run python -m data_pipeline.src.assets.sync_fly_images --scope pax-only"'
```

Count image files on Fly volume:
```bash
fly ssh console -a pax-tt-app-dev -C 'sh -lc "find /data/images/games -type f | wc -l"'
```

## 12. R2 Commands (Backup-Only)

R2 dry run candidates:
```bash
poetry run python -m data_pipeline.src.assets.sync_r2_images --dry-run --scope all-qualified --max-rank 10000 2>&1 \
  | awk -F': ' '/Candidates selected/ {print $2}'
```

Count R2 objects:
```bash
export AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"
export AWS_DEFAULT_REGION="${R2_REGION:-auto}"
aws s3 ls "s3://$R2_BUCKET_NAME" --recursive --summarize \
  --endpoint-url "$R2_ENDPOINT_URL"
```
