# Backend

## Scope
- FastAPI application runtime, database models/migrations, recommendation service logic, and backend tests.

## Key Paths
- `app/`: API routes, models, CRUD, runtime profile, auth, recommendation engine.
- `alembic/` + `alembic.ini`: database migration history and config.
- `scripts/`: backend-local startup/import helpers used in container and maintenance workflows.
- `tests/`: backend unit/integration tests.

## Local Run
```bash
poetry run python -m backend.app.runtime_profile --serve
```

Optional direct development server:
```bash
poetry run uvicorn backend.app.main:app --reload
```

## Migrations
Run migrations from repo root:
```bash
poetry run alembic upgrade head
```

## Tests
Run backend tests:
```bash
poetry run pytest backend/tests -q
```

Run targeted suites:
```bash
poetry run pytest backend/tests/test_db_keepalive.py -q
poetry run pytest backend/tests/test_runtime_profile.py -q
```
