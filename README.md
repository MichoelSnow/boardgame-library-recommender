# Boardgame Library Recommender

## Summary

A board game recommendation system built around BoardGameGeek data, collaborative filtering, and practical library use.

The project started as a way to make game discovery faster and more trustworthy in real-world settings where people need good suggestions quickly, given a limited tabletop library. It combines a data pipeline that ingests and models BGG data, a backend API that serves recommendations and search/filter endpoints.

This repository is intentionally operations-aware: deployment, validation, rollback, and incident checks are treated as first-class workflows, not afterthoughts. The goal is to keep recommendation quality high while making runtime behavior predictable under load and easy to operate as a solo-maintained system.

## Key Features

- Collaborative-filtering recommendations using sparse embeddings and similarity scoring
- Library-specific game lists via configurable BoardGameGeek ID imports 
- BoardGameGeek-backed game corpus with ratings, mechanics, categories, and metadata
- User auth and suggestion capture workflows for feedback-driven iteration
- Advanced game discovery filters for player count, complexity, categories, mechanics, and more
- Performance-oriented runtime design (query tuning, caching, profiling, validation gates)
- Production deployment on Fly.io with runbook-driven deploy/rollback procedures

## Repository Layout

```text
bg_lib_recommender/
├── backend/        # FastAPI runtime, models/migrations, backend tests
├── frontend/       # React SPA
├── data_pipeline/  # Ingest/transform/features/assets + notebooks
├── scripts/        # Deploy/validation/alerts/db/perf/load utilities
├── docs/           # Runbooks, policies, architecture, ADRs, roadmaps
├── data/           # Local generated data artifacts (ignored)
└── logs/           # Local logs and deploy trace artifacts (ignored)
```

## Quick Start

For first-time setup and deployment, use the installation guide:

- [docs/installation/deployment.md](docs/installation/deployment.md)

This covers:

- clone -> local SQLite
- clone -> local Postgres
- clone -> Fly.io Postgres from scratch

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
- Library-aware filtering support

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
- Configurable runtime profile behavior for operations during library hours

For detailed architecture and policy docs, use the docs index:
- [docs/README.md](docs/README.md)

## Docs

- Roadmap:
  - [docs/active/backlog.md](docs/active/backlog.md)
- Core docs:
  - [docs/core/README.md](docs/core/README.md)
  - [docs/installation/deployment.md](docs/installation/deployment.md)
  - [docs/core/architecture.md](docs/core/architecture.md)
  - [docs/core/runbook.md](docs/core/runbook.md)
  - [docs/core/security.md](docs/core/security.md)
- Domain READMEs:
  - [backend/README.md](backend/README.md)
  - [frontend/README.md](frontend/README.md)
  - [data_pipeline/README.md](data_pipeline/README.md)
  - [scripts/README.md](scripts/README.md)
- Full docs index:
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

## Contributing

1. Create a feature branch from `main`.
2. Implement changes with tests/docs updates.
3. Open a pull request.
4. Run the relevant validation workflow for the target environment.

## License

This project is licensed under the MIT License. See `LICENSE`.
