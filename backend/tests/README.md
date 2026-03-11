# Backend Tests

## Scope
- API contract/behavior tests
- CRUD/recommender logic tests
- runtime/deploy profile validation tests
- script-level smoke tests for deploy/alert flows

## Prerequisites
- From repo root: `poetry install`
- No external network calls are required for core backend unit/API tests.
- Keep test commands bounded when iterating locally:
  - `timeout 10s poetry run pytest <path> -q`

## Common Commands

Run the focused API contract set:

```bash
poetry run pytest backend/tests/test_api_endpoints.py -q
```

Run the full backend suite:

```bash
poetry run pytest backend/tests -q
```

Run deploy/alert script tests:

```bash
poetry run pytest backend/tests/test_fly_postgres_backup.py backend/tests/test_fly_postgres_restore.py -q
poetry run pytest backend/tests/test_run_prod_health_alerts.py backend/tests/test_validate_prod_alert_path.py -q
```

Run performance smoke test (requires local app server on `localhost:8000`):

```bash
poetry run pytest backend/tests/test_performance.py -q
```

## Runtime Expectations (Typical Local)
- `test_api_endpoints.py`: ~1-5s
- Targeted unit file: <2s
- `backend/tests` full run: usually under a few minutes depending on machine load
- `test_performance.py`: depends on running server state and local DB size

## Notes
- `test_performance.py` is a smoke/perf check; run it after booting the app.
- Legacy utility script `backend/tests/create_indexes.py` is not part of the pytest suite.
