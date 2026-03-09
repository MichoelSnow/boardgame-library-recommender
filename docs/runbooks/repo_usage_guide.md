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

## 1. Local Setup

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

## 2. Run the App Locally

Backend:

```bash
poetry run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Note:
- `backend.app.runtime_profile --serve` is for runtime-profile/server-mode bootstrapping and currently defaults to port `8080`.

Frontend:

```bash
cd frontend
npm start
```

## 3. Data Pipeline Workflow

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

## 4. Import Processed Data into Backend

Ensure schema is current:

```bash
poetry run alembic upgrade head
```

Import processed game/entity data:

```bash
poetry run python backend/app/import_data.py
```

Import and trigger R2 image sync for qualifying games (top rank + PAX):

```bash
poetry run python backend/app/import_data.py --sync-images-r2 --sync-images-max-rank 10000
```

Optional full refresh:

```bash
poetry run python backend/app/import_data.py --delete-existing
```

Import PAX data:

```bash
poetry run python backend/app/import_pax_data.py
```

Import PAX data and sync PAX image set to R2:

```bash
poetry run python backend/app/import_pax_data.py --sync-images-r2
```

Manual R2 image sync script:

```bash
poetry run python -m data_pipeline.src.assets.sync_r2_images --scope all-qualified --max-rank 10000
```

R2 bucket policy note:
- Use one shared `R2_BUCKET_NAME` across local/dev/prod.
- Do not split images into separate dev/prod buckets unless isolation requirements outweigh storage-cost goals.

## 5. Fly Stack Operations (Dev/Prod)

Use stack helper commands:

```bash
scripts/deploy/fly_stack.sh dev up
scripts/deploy/fly_stack.sh dev down
scripts/deploy/fly_stack.sh prod up
scripts/deploy/fly_stack.sh prod down
```

See:
- [fly_stack_operations.md](fly_stack_operations.md)

## 6. Validation Workflows

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

## 7. Deploy and Rollback

Canonical deploy/rollback entrypoint:
- [deploy_rollback_runbook.md](deploy_rollback_runbook.md)

Direct runbooks:
- [deploy_dev_runbook.md](deploy_dev_runbook.md)
- [deploy_prod_runbook.md](deploy_prod_runbook.md)
- [rollback_runbook.md](rollback_runbook.md)
