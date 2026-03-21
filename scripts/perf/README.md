# Performance Scripts

## `benchmark_recommendation_size.py`
- What it does:
  - Benchmarks recommendation latency versus liked-game list size.
- When to use:
  - Recommendation performance analysis and regression checks.
- How to use:
```bash
poetry run python scripts/perf/benchmark_recommendation_size.py \
  --env dev \
  --game-ids "224517,167791,174430,173346,266192" \
  --sizes "1,5,10,20,35,50" \
  --iterations 20 \
  --limit 5 \
  --library-only true
```

## `profile_hot_endpoints.py`
- What it does:
  - Profiles hot API endpoints in-process using FastAPI `TestClient`.
  - Captures per-endpoint response latency and SQL query behavior:
    - query count
    - total SQL time
    - top SQL statements by cumulative time
- When to use:
  - Phase 11 query/N+1 analysis and targeted optimization planning.
- How to use:
```bash
# Default public endpoints
poetry run python scripts/perf/profile_hot_endpoints.py --iterations 10

# Live dev machine (Fly) over HTTP
poetry run python scripts/perf/profile_hot_endpoints.py \
  --environment dev \
  --iterations 10

# Include admin endpoints (requires admin creds via args or env)
poetry run python scripts/perf/profile_hot_endpoints.py \
  --iterations 10 \
  --include-admin \
  --admin-username "${SMOKE_TEST_USERNAME}" \
  --admin-password "${SMOKE_TEST_PASSWORD_DEV}"
```
- Output:
  - Writes JSON report to `logs/profiling/backend_queries/hot_endpoints.<timestamp>.json`
- Notes:
  - `--environment local` includes SQL query-count/time metrics (in-process).
  - `--environment dev|prod` profiles live Fly endpoints over HTTP and reports latency/status; SQL query metrics are not available in that mode.
