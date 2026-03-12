# Backend

## Scope
- FastAPI application runtime, database models/migrations, recommendation service logic, and backend tests.

For full repository usage flows, see:
- [docs/ai/repo_map.md](../docs/ai/repo_map.md)

## Key Paths
- `app/`: API routes, models, CRUD, runtime profile, auth, recommendation engine.
- `alembic/` + `alembic.ini`: database migration history and config.
- `scripts/`: backend-local startup/import helpers used in container and maintenance workflows.
- `tests/`: backend unit/integration tests.

## Local Run
```bash
poetry run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Optional runtime-profile bootstrap:
```bash
poetry run python -m backend.app.runtime_profile --serve
```

### Development Server Notes
- Interactive API docs: `http://localhost:8000/docs`
- OpenAPI schema: `http://localhost:8000/openapi.json`
- CORS is configured for local frontend development.
- Timeout guards exist on long-running API paths to avoid hanging requests.
- `runtime_profile --serve` currently defaults to port `8080`.

## Migrations
Run migrations from repo root:
```bash
poetry run alembic upgrade head
```

## Local Data Imports
Import latest processed board game data:

```bash
poetry run python backend/app/import_data.py
```

Optional reset import:

```bash
poetry run python backend/app/import_data.py --delete-existing
```

Import PAX dataset:

```bash
poetry run python backend/app/import_pax_data.py
```

## Tests
Run backend tests:
```bash
poetry run pytest backend/tests -q
```

Run targeted suites:
```bash
poetry run pytest backend/tests/test_db_queries.py -q
poetry run pytest backend/tests/test_db_keepalive.py -q
poetry run pytest backend/tests/test_runtime_profile.py -q
poetry run pytest backend/tests/test_performance.py -q
poetry run python backend/tests/create_indexes.py
```

### Test File Guide
- `test_db_queries.py`
  - Basic database query behavior and non-hanging query paths.
- `test_performance.py`
  - Endpoint performance checks (requires app server running).
- `create_indexes.py`
  - Utility script to create/refresh index set used in local perf testing.

### Performance Expectations
- Canonical SLO/latency targets live in:
  - [docs/core/ownership_and_slos.md](../docs/core/ownership_and_slos.md)
- Validation gate checks (via `scripts/validate/validate_performance_gate.py`) enforce environment-level thresholds for:
  - `/api`
  - `/api/version`
  - `/api/recommendations/{game_id}`

## Logging
- Standard log files are documented in:
  - [logs/README.md](../logs/README.md)
- Common local tails:

```bash
tail -f logs/import_data.log
tail -f logs/import_pax_data.log
tail -f logs/get_game_data.log
tail -f logs/get_ratings.log
```

## Production Configuration Notes
- In Fly-hosted production, use `DATABASE_URL` (Postgres).
- Do not rely on SQLite fallback in production.
- Core auth/runtime variables include:
  - `SECRET_KEY`
  - `ALGORITHM`
  - `ACCESS_TOKEN_EXPIRE_MINUTES`
- Canonical deploy/runtime procedures:
  - [docs/core/runbook.md](../docs/core/runbook.md)
  - [docs/core/runbook.md](../docs/core/runbook.md)

## API Endpoints (Primary)

### Core
- `GET /api`
- `GET /api/version`

### Games and Recommendations
- `GET /api/games/`
- `GET /api/games/{game_id}`
- `GET /api/recommendations/{game_id}`
- `POST /api/recommendations`
- `GET /api/recommendations/status`
- `GET /api/filter-options/`
- `GET /api/mechanics/`
- `GET /api/categories/`
- `GET /api/mechanics/by_frequency`
- `GET /api/categories/by_frequency`
- `GET /api/pax_game_ids`

### Auth and Users
- `POST /api/token`
- `POST /token` (legacy compatibility endpoint)
- `POST /api/users/` (admin required)
- `GET /api/users/me/`
- `PUT /api/users/me/password`

### Suggestions
- `POST /api/suggestions/`

### Image Proxy
- `GET /api/proxy-image/{url:path}`
