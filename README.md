# PAX Tabletop Recommender

A board game recommendation system built around BoardGameGeek data, collaborative filtering, and practical convention use.

The project started as a way to make game discovery faster and more trustworthy in real-world settings where people need good suggestions quickly, especially at PAX tabletop events. It combines a data pipeline that ingests and models BGG data, a backend API that serves recommendations and search/filter endpoints, and a frontend built for quick iteration during active convention windows.

This repository is intentionally operations-aware: deployment, validation, rollback, and incident checks are treated as first-class workflows, not afterthoughts. The goal is to keep recommendation quality high while making runtime behavior predictable under load and easy to operate as a solo-maintained system.

## Key Features

- Collaborative-filtering recommendations using sparse embeddings and similarity scoring
- PAX convention integration with PAX-focused filtering and runtime profile support
- BoardGameGeek-backed game corpus with ratings, mechanics, categories, and metadata
- User auth and suggestion capture workflows for feedback-driven iteration
- Advanced game discovery filters for player count, complexity, categories, mechanics, and more
- Performance-oriented runtime design (query tuning, caching, profiling, validation gates)
- Production deployment on Fly.io with runbook-driven deploy/rollback procedures

## Repository Layout

```text
pax_tt_recommender/
├── backend/        # FastAPI runtime, models/migrations, backend tests
├── frontend/       # React SPA
├── data_pipeline/  # Ingest/transform/features/assets + notebooks
├── scripts/        # Deploy/validation/alerts/db/perf/load utilities
├── docs/           # Runbooks, policies, architecture, ADRs, roadmaps
├── data/           # Local generated data artifacts (ignored)
└── logs/           # Local logs and deploy trace artifacts (ignored)
```

## Start Here

- Core docs index: [docs/README.md](docs/README.md)
- Practical repo usage guide: [repo_usage_guide.md](docs/ai/repo_map.md)
- Deploy + rollback entrypoint: [deploy_rollback_runbook.md](docs/core/runbook.md)
- Migration/phase tracking: [best_practices_migration_guide.md](docs/active/best_practices_migration_guide.md)
- Convention readiness gate: [pre_convention_readiness_checklist.md](docs/active/pre_convention_readiness_checklist.md)

## Domain READMEs

- Backend: [backend/README.md](backend/README.md)
- Frontend: [frontend/README.md](frontend/README.md)
- Data pipeline: [data_pipeline/README.md](data_pipeline/README.md)
- Scripts: [scripts/README.md](scripts/README.md)

## Quick Start (Local)

### 1) Install dependencies

```bash
poetry install
cd frontend && npm ci
```

### 2) Configure environment

Create `.env` in repo root with at minimum:

```env
SECRET_KEY=<32+ char secret>
DATABASE_PATH=backend/database/boardgames.db
BGG_USERNAME=<optional for pipeline ingestion>
BGG_PASSWORD=<optional for pipeline ingestion>
```

For auth/release validation flows, set optional smoke-test and admin vars documented in backend/scripts runbooks.

### 3) Run backend

```bash
poetry run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

`backend.app.runtime_profile --serve` is intended for runtime-profile/server-mode bootstrapping and currently defaults to port `8080`.

### 4) Run frontend

```bash
cd frontend
npm start
```

## Common Workflows

### Data pipeline

Run stage modules (details in data pipeline README):

```bash
poetry run python -m data_pipeline.src.ingest.get_ranks
poetry run python -m data_pipeline.src.ingest.get_game_data
poetry run python -m data_pipeline.src.ingest.get_ratings
poetry run python -m data_pipeline.src.transform.data_processor
poetry run python -m data_pipeline.src.features.create_embeddings
```

### Dev/Prod stack orchestration

```bash
scripts/deploy/fly_stack.sh dev up
scripts/deploy/fly_stack.sh dev down
scripts/deploy/fly_stack.sh prod up
scripts/deploy/fly_stack.sh prod down
```

### Validation

```bash
poetry run python scripts/validate/validate_dev_deploy.py
poetry run python scripts/validate/validate_prod_release.py
```

Notebook hygiene checks:

```bash
python scripts/validate/validate_notebook_outputs.py
python scripts/validate/validate_notebook_secrets.py
```

## Architecture Overview

### System Architecture

1. **Data pipeline**: BoardGameGeek ingest, normalization, and feature generation produce recommendation artifacts and importable datasets.
2. **Backend API**: FastAPI + SQLAlchemy provide auth, game discovery/filtering, recommendation APIs, and operational endpoints.
3. **Frontend SPA**: React + MUI provide browse/search/filter/recommendation and suggestion flows.
4. **Deployment/operations**: Dockerized deploys on Fly.io, runbook-driven validation, and explicit rollback paths.

### Key Components

#### Recommendation Engine (`backend/app/recommender.py`)
- `ModelManager` singleton with lazy-loading lifecycle for embedding artifacts
- Collaborative filtering recommendations with cosine-style similarity over sparse embeddings
- Support for disliked games (anti-recommendation signals)
- Degraded-mode behavior and health signaling when model artifacts are unavailable
- PAX-aware filtering support

#### Authentication and Authorization (`backend/app/security.py`, `backend/app/main.py`)
- JWT bearer token authentication
- Secure password hashing (`passlib` + bcrypt)
- User/admin role checks on protected flows

#### Data Pipeline (`data_pipeline/src/`)
- `ingest/`: ranks, game metadata, and ratings collection
- `transform/`: normalization and table-oriented processing
- `features/`: embedding and recommender feature artifact generation
- `assets/`: image and related asset helpers

#### Performance and Runtime Controls
- Query and relationship-loading optimizations in backend CRUD/recommender paths
- API/runtime validation gates and load-rehearsal tooling under `scripts/validate` and `scripts/load`
- Configurable runtime profile behavior for convention and non-convention operation

For detailed architecture and policy docs, use the docs index:
- [docs/README.md](docs/README.md)

## Technology Stack

### Backend
- FastAPI
- SQLAlchemy
- Alembic
- JWT (`python-jose`)
- Password hashing (`passlib[bcrypt]`)
- NumPy / SciPy / scikit-learn (recommendation computations)
- Pandas (data processing)

### Frontend
- React 18
- Material UI
- TanStack React Query
- React Router
- Axios

### Data Collection and Processing
- Selenium
- Requests
- BeautifulSoup4

### Deployment
- Docker
- Fly.io
- Postgres for Fly-hosted environments
- SQLite support for local/offline workflows where explicitly configured

## Notes

- Canonical release/version policy: [deploy_policy_and_prereqs.md](docs/core/runbook.md)
- Canonical release-note format: [release_notes_standard.md](docs/ai/standards.md)
- Repository structure and placement rules: [repository_structure_policy.md](docs/ai/repo_map.md)

## Contributing

1. Create a feature branch from `main`.
2. Implement changes with tests/docs updates.
3. Open a pull request.
4. Run the relevant validation workflow for the target environment.

## License

This project is licensed under the MIT License. See `LICENSE`.
