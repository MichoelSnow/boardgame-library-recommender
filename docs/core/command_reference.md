# Command Reference

Use this file for common operational commands that are easy to forget.

## 0. Environment Bootstrap

Load environment variables from local `.env`:

```bash
set -a && source .env && set +a
```

Fly app variable conventions used below:
- `FLY_APP_NAME_DEV`, `FLY_APP_NAME_PROD`
- `FLY_DB_APP_NAME_DEV`, `FLY_DB_APP_NAME_PROD`

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

Data pipeline and import workflow details:
- [data_pipeline/README.md](/data_pipeline/README.md)
- [backend/README.md](/backend/README.md)


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
fly ssh console -a "${FLY_APP_NAME_DEV}" -C 'sh -lc "cd /app/backend && poetry run alembic upgrade head"'
fly ssh console -a "${FLY_APP_NAME_PROD}" -C 'sh -lc "cd /app/backend && poetry run alembic upgrade head"'
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

Check runtime DB URL locally and get most recent suggestions from sqlite and postgres:

```bash
poetry run python -c "from backend.app.db_config import get_database_url; print(get_database_url())"

sqlite3 backend/database/boardgames.db "SELECT id, user_id, comment, timestamp FROM user_suggestions ORDER BY timestamp DESC LIMIT 20;"

psql "$DATABASE_URL" -c "SELECT id, user_id, comment, timestamp FROM user_suggestions ORDER BY timestamp DESC LIMIT 20;"
```

Get Most recent suggestions from fly in dev and prod:

```bash
fly ssh console -a "${FLY_DB_APP_NAME_DEV}" -C 'sh -lc "psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c \"SELECT id, user_id, comment, timestamp FROM user_suggestions ORDER BY timestamp DESC LIMIT 20;\""'

fly ssh console -a "${FLY_DB_APP_NAME_PROD}" -C 'sh -lc "psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c \"SELECT id, user_id, comment, timestamp FROM user_suggestions ORDER BY timestamp DESC LIMIT 20;\""'
```

## 6. Quality Gates

Python:
```bash
poetry run ruff format --check backend data_pipeline scripts
poetry run ruff check backend data_pipeline scripts
```

Frontend:
```bash
cd frontend
npm run lint
npm run build
npm audit --omit=dev --json > /tmp/npm_audit.json
python ../scripts/validate/validate_frontend_audit.py
```

## 7. Security Scans

Local:
```bash
# Secret scanning
gitleaks detect --source . --no-git

# Notebook secret-pattern scan
poetry run python scripts/validate/validate_notebook_secrets.py

# Frontend audit policy check
poetry run python scripts/validate/validate_frontend_audit.py

# Python dependency audit policy check
poetry run python scripts/validate/validate_python_audit.py
```

CI mapping:
```text
security job:
- gitleaks
- validate_notebook_outputs.py
- validate_notebook_secrets.py

frontend-audit job:
- validate_frontend_audit.py

python-quality job:
- validate_python_audit.py
```

## 8. DB Backup and Restore

Backup:

```bash
poetry run python scripts/db/fly_postgres_backup.py --env dev
poetry run python scripts/db/fly_postgres_backup.py --env prod --output /tmp/bg-lib-prod-backup.sql
```

Restore:

```bash
poetry run python scripts/db/fly_postgres_restore.py --env dev --input /tmp/bg-lib-dev-backup.sql
poetry run python scripts/db/fly_postgres_restore.py --env prod --input /tmp/bg-lib-prod-backup.sql --restore-db bg_lib_recommender_restore_test
```

## 9. Incident Triage

Machine state:

```bash
fly machines list -a "${FLY_APP_NAME_DEV}"
fly machines list -a "${FLY_DB_APP_NAME_DEV}"
fly machines list -a "${FLY_APP_NAME_PROD}"
fly machines list -a "${FLY_DB_APP_NAME_PROD}"
```

App logs:

```bash
fly logs -a "${FLY_APP_NAME_DEV}" | tee -a "logs/${FLY_APP_NAME_DEV}.fly.log"
fly logs -a "${FLY_APP_NAME_PROD}" | tee -a "logs/${FLY_APP_NAME_PROD}.fly.log"
```

Common error patterns:

```bash
fly logs -a "${FLY_APP_NAME_DEV}" | rg -n "ERROR|CRITICAL|WORKER TIMEOUT|Out of memory|Killed process|Traceback"
fly logs -a "${FLY_APP_NAME_PROD}" | rg -n "ERROR|CRITICAL|WORKER TIMEOUT|Out of memory|Killed process|Traceback"
```

## 10. Alerting and Workflow Toggles

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

## 11. Release and Rollback Helpers

Record deploy traceability:

```bash
poetry run python scripts/deploy/record_deploy_traceability.py --env prod --marker prod-promotion --expected-sha-path .tmp/validated_dev_sha.txt
```

Prepare rollback target:

```bash
poetry run python scripts/deploy/prepare_fly_rollback.py --env prod
```

## 12. Load and Performance

Recommendation size benchmark:

```bash
poetry run python scripts/perf/benchmark_recommendation_size.py --env dev --game-ids "<csv>" --sizes "1,5,10,20,35,50" --iterations 20 --limit 5 --library-only true
```

k6 rehearsal:

```bash
k6 run \
  -e BASE_URL="https://${FLY_APP_NAME_DEV}.fly.dev" \
  -e GAME_IDS="<csv>" \
  -e VUS="10" \
  -e DURATION="3m" \
  -e THINK_TIME_SECONDS="2.0" \
  scripts/load/k6_rehearsal.js
```

## 13. Fly Image Seed (Primary)

Seed all qualified images directly from BGG to Fly dev volume:

```bash
fly ssh console -a "${FLY_APP_NAME_DEV}" -C 'sh -lc "cd /app && poetry run python -m data_pipeline.src.assets.sync_fly_images --scope all-qualified --max-rank 10000"'
```

Dry run candidate count:

```bash
fly ssh console -a "${FLY_APP_NAME_DEV}" -C 'sh -lc "cd /app && poetry run python -m data_pipeline.src.assets.sync_fly_images --scope all-qualified --max-rank 10000 --dry-run"'
```

Library-only seed:
```bash
fly ssh console -a "${FLY_APP_NAME_DEV}" -C 'sh -lc "cd /app && poetry run python -m data_pipeline.src.assets.sync_fly_images --scope library-only"'
```

Count image files on Fly volume:
```bash
fly ssh console -a "${FLY_APP_NAME_DEV}" -C 'sh -lc "find /data/images/games -type f | wc -l"'
```
