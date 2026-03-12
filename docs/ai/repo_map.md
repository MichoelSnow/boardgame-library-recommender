# AI Repo Map

## System Overview
- Backend: FastAPI + SQLAlchemy in `backend/app/`
- Frontend: React app in `frontend/src/`
- Data pipeline: ingest/transform/features under `data_pipeline/src/`
- Deployment/runtime scripts: `scripts/`

## Core Code Areas
- Backend API: `backend/app/`
- Backend tests: `backend/tests/`
- Data pipeline: `data_pipeline/src/`
- Frontend app: `frontend/src/`
- Operational scripts: `scripts/`

## Operational Docs
- Human canonical docs: `docs/core/`
- In-progress docs: `docs/active/`

## High-Value Entry Points
- API app/startup/security middleware: `backend/app/main.py`
- Recommendation logic: `backend/app/recommender.py`, `data_pipeline/src/features/recommender.py`
- Data import paths: `backend/app/import_data.py`, `backend/app/import_pax_data.py`
- Deploy/validation scripts: `scripts/deploy/`, `scripts/validate/`
- DB models and API schemas: `backend/app/models.py`, `backend/app/schemas.py`

## Task Touchpoints
- Add/modify game filters:
  - `backend/app/crud.py`
  - affected request/response models in `backend/app/schemas.py`
  - frontend filter UI in `frontend/src/components/`
- Modify recommendation behavior:
  - `backend/app/recommender.py`
  - pipeline feature generation in `data_pipeline/src/features/`
  - recommendation API usage paths in frontend components
- Schema/data model changes:
  - `backend/app/models.py`
  - Alembic migrations in `backend/alembic/`
  - import/migration scripts under `backend/app/` and `backend/scripts/`

## Repo Structure Rules
- Keep runtime code out of `docs/` and notebooks.
- Keep scripts task-specific under `scripts/<domain>/`.
- Keep archived/deprecated docs as non-canonical references only.
