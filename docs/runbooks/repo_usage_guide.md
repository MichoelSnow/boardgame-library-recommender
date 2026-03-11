# Repo Usage Guide

This guide is the practical "how to use the repo" entrypoint.

Use this file when you need to run the system locally, refresh data, import data, validate a deploy, or operate Fly dev/prod stacks.

For a quick command lookup, use:
- [command_reference.md](command_reference.md)

## Domain READMEs

- Backend: [backend/README.md](../../backend/README.md)
- Frontend: [frontend/README.md](../../frontend/README.md)
- Data pipeline: [data_pipeline/README.md](../../data_pipeline/README.md)
- Scripts: [scripts/README.md](../../scripts/README.md)
- Logs: [logs/README.md](../../logs/README.md)

## Test Prerequisites and Runtime Expectations

Minimum local prerequisites:
- `poetry install`
- `cd frontend && npm ci`
- For backend performance smoke tests only: local backend server running on `localhost:8000`

Recommended bounded test command pattern while iterating:

```bash
timeout 10s poetry run pytest <test-path> -q
```

Typical local runtime ranges:
- Backend targeted test module: ~1-10s
- Backend full suite: typically under a few minutes
- Frontend unit/integration tests: typically under a few minutes
- Data pipeline unit tests: usually seconds to low minutes

## Workflow A: Local Development (Complete Flow)

Use this workflow when running entirely on your local machine.

### A1. Setup

Install Python dependencies and frontend packages:

```bash
poetry install
cd frontend && npm ci
```

Create `.env` in the repository root with at least:

```env
SECRET_KEY=<32+ char secret>
DATABASE_PATH=backend/database/boardgames.db
BGG_USERNAME=<optional for pipeline ingest>
BGG_PASSWORD=<optional for pipeline ingest>
```

### A2. Run the App Locally

Backend:

```bash
export IMAGE_BACKEND="${IMAGE_BACKEND:-bgg_proxy}"
poetry run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Note:
- `backend.app.runtime_profile --serve` is for runtime-profile/server-mode bootstrapping and currently defaults to port `8080`.
- `IMAGE_BACKEND=bgg_proxy` is the local default path; Fly deploys use `IMAGE_BACKEND=fly_local`.

Frontend:

```bash
cd frontend
npm start
```

### A3. Run Data Pipeline (Optional Local Refresh)

Run these in order:

```bash
poetry run python -m data_pipeline.src.ingest.get_ranks
poetry run python -m data_pipeline.src.ingest.get_game_data
poetry run python -m data_pipeline.src.ingest.get_ratings
poetry run python -m data_pipeline.src.transform.data_processor
poetry run python -m data_pipeline.src.features.create_embeddings
```

See full details (outputs, resume behavior, DuckDB ratings backend) in:
- [data_pipeline/README.md](../../data_pipeline/README.md)

### A4. Import Processed Data Locally

Ensure schema is current:

```bash
poetry run alembic upgrade head
```

Import processed game/entity data:

```bash
poetry run python backend/app/import_data.py
```

Optional full refresh:

```bash
poetry run python backend/app/import_data.py --delete-existing
```

Import PAX data:

```bash
poetry run python backend/app/import_pax_data.py
```

### A5. Validate Local Behavior (Optional)

Basic local smoke checks (with backend running on `localhost:8000`):

```bash
curl -sSf http://localhost:8000/api/version
curl -sSf http://localhost:8000/api/recommendations/224517
```

## Workflow B: Fly Dev/Prod Operations (Complete Flow)

Use this workflow when operating deployed environments. Run in order.

Rollout policy:
- Validate all new architecture/runtime changes in `dev` first.
- Do not run equivalent `prod` steps until changes are merged to `main` and promoted.

### B1. Start Environment Machines First

Dev:

```bash
scripts/deploy/fly_stack.sh dev up
```

Prod:

```bash
scripts/deploy/fly_stack.sh prod up
```

Related runbook:
- [fly_stack_operations.md](fly_stack_operations.md)

### B2. Deploy and Migrate (If Needed)

Canonical deploy/rollback runbooks:
- [deploy_rollback_runbook.md](deploy_rollback_runbook.md)
- [deploy_dev_runbook.md](deploy_dev_runbook.md)
- [deploy_prod_runbook.md](deploy_prod_runbook.md)
- [rollback_runbook.md](rollback_runbook.md)

Deploy app with SHA and build timestamp:

```bash
scripts/deploy/fly_deploy.sh dev
scripts/deploy/fly_deploy.sh prod
```

Apply migrations after deploy when required:

```bash
fly ssh console -a pax-tt-app-dev -C 'sh -lc "cd /app/backend && poetry run alembic upgrade head"'
fly ssh console -a pax-tt-app -C 'sh -lc "cd /app/backend && poetry run alembic upgrade head"'
```

### B3. Image Operations (Dev/Prod)

Canonical image operations live in:
- [image_storage_operations.md](image_storage_operations.md)

Most-used commands:

Count image files on dev/prod app volumes:

```bash
fly ssh console -a pax-tt-app-dev -C 'sh -lc "find /data/images/games -type f | wc -l"'
fly ssh console -a pax-tt-app -C 'sh -lc "find /data/images/games -type f | wc -l"'
```

Primary seed path (BGG -> Fly local volume):

```bash
fly ssh console -a pax-tt-app-dev -C 'sh -lc "cd /app && poetry run python -m data_pipeline.src.assets.sync_fly_images --scope all-qualified --max-rank 10000"'
fly ssh console -a pax-tt-app -C 'sh -lc "cd /app && poetry run python -m data_pipeline.src.assets.sync_fly_images --scope all-qualified --max-rank 10000"'
```

Note:
- Use BGG -> Fly local seeding as first-line workflow.
- Cloudflare/R2 operations are backup-only. Use:
  - [image_storage_operations.md#9-cloudflare-r2-backup-commands](image_storage_operations.md#9-cloudflare-r2-backup-commands)

### B4. Validate Deploy/Release

Dev deploy validation:
```bash
poetry run python scripts/validate/validate_dev_deploy.py
```

Prod release validation:
```bash
poetry run python scripts/validate/validate_prod_release.py
```

Notebook hygiene:

```bash
python scripts/validate/validate_notebook_outputs.py
python scripts/validate/validate_notebook_secrets.py
```

### B5. Stop Environment Machines (When Done)

```bash
scripts/deploy/fly_stack.sh dev down
scripts/deploy/fly_stack.sh prod down
```

## Workflow C: Quality Commands (Local)

Use these commands before opening a PR when you change backend/frontend/runtime behavior.

### C1. Python Quality

Install/update toolchain:

```bash
poetry install --with dev
```

Format/lint/type-check:

```bash
poetry run ruff format --check backend data_pipeline scripts
poetry run ruff check backend data_pipeline scripts
poetry run mypy backend/app/db_config.py backend/app/db_keepalive.py backend/app/runtime_profile.py
```

Deterministic backend/pipeline test subset (matches CI):

```bash
poetry run pytest -q \
  backend/tests/test_api_endpoints.py \
  backend/tests/test_convention_kiosk.py \
  backend/tests/test_crud_helpers.py \
  backend/tests/test_db_config.py \
  backend/tests/test_db_keepalive.py \
  backend/tests/test_fly_postgres_backup.py \
  backend/tests/test_fly_postgres_restore.py \
  backend/tests/test_image_cache_fill.py \
  backend/tests/test_player_filter.py \
  backend/tests/test_recommendation_payload.py \
  backend/tests/test_recommender_degraded_mode.py \
  backend/tests/test_recommender_pax_only.py \
  backend/tests/test_run_prod_health_alerts.py \
  backend/tests/test_runtime_profile.py \
  backend/tests/test_sqlite_to_postgres_migration.py \
  backend/tests/test_sync_fly_images.py \
  backend/tests/test_validate_prod_alert_path.py \
  backend/tests/test_versioning.py \
  data_pipeline/tests
```

### C2. Frontend Quality

Install dependencies:

```bash
cd frontend
npm ci
```

Lint/format/build/tests:

```bash
npm run lint
npm run build
npm run test:ci -- \
  src/api/client.test.js \
  src/api/auth.test.js \
  src/hooks/useConventionUiState.test.js \
  src/hooks/useRecommendationSessionState.test.js \
  src/utils/imageUrls.test.js \
  src/components/GameDetails.test.js \
  src/integration/authFlow.test.js \
  src/integration/gameFilteringFlow.test.js \
  src/integration/recommendationFlow.test.js
```

### C3. CI Job Mapping

- `python-quality`:
  - `poetry check`
  - repo-wide `ruff format --check` on `backend`, `data_pipeline`, and `scripts`
  - repo-wide `ruff check` on `backend`, `data_pipeline`, and `scripts`
  - `compileall`
  - critical-module `mypy`
  - deterministic backend/pipeline pytest subset
- `frontend-build`:
  - `npm run lint`
  - `npm run build`
  - frontend targeted tests (unit + integration)
- `frontend-audit`:
  - `npm audit --omit=dev --json` validated via `scripts/validate/validate_frontend_audit.py`
  - fails only on new high/critical packages beyond `.github/npm_audit_allowlist.json`

### C4. Troubleshooting

- `poetry.lock` / dependency drift:
  - run `poetry lock && poetry install --with dev` and commit updated lockfile.
- Frontend dependency drift:
  - run `npm install` (or `npm ci` after lock update), then commit `frontend/package-lock.json`.
- `mypy` import noise from third-party packages:
  - keep checks scoped to listed critical modules unless we intentionally expand coverage.
- Repo-wide formatting drift:
  - run `poetry run ruff format backend data_pipeline scripts` to apply formatting before re-running checks.
- Frontend audit fails due baseline drift:
  - run `npm audit --omit=dev --json` in `frontend` and compare package names against `.github/npm_audit_allowlist.json`.
  - only add allowlist entries intentionally with rationale in PR description.
- React `act(...)` warnings in frontend tests:
  - currently expected with existing testing-library version; scheduled for toolchain upgrade phase.
