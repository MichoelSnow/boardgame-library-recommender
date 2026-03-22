# Phase 11 Query Profiling Notes (2026-03-20)

Source artifact:
- `logs/profiling/backend_queries/hot_endpoints.20260320T161003Z.json`

Command used:
```bash
poetry run python scripts/perf/profile_hot_endpoints.py --environment dev --iterations 10
```

## Current Findings (dev)

1. `GET /api/filter-options/` is the slowest hot endpoint in this sample:
- p50: `535.73ms`
- p95: `780.38ms`
- max: `3414.32ms`

2. `GET /api/games/224517` has a significant tail outlier:
- p50: `251.55ms`
- p95: `262.69ms`
- max: `4060.28ms`

3. Other sampled endpoints were comparatively stable:
- `GET /api/games/?limit=24&skip=0&sort_by=rank`
- `GET /api/recommendations/224517?limit=24`

## Profiling Mode Limitation

The run was executed with `--environment dev`, which profiles live HTTP latency/status only.

- `sql_metrics_available=false`
- No SQL query count/time in this artifact
- N+1 cannot be confirmed directly from this remote-only report

For SQL-level diagnosis, run local mode:
```bash
poetry run python scripts/perf/profile_hot_endpoints.py --environment local --iterations 10
```

## Recommended Next Changes (targeted, low-risk)

1. Optimize `get_game` path (`/api/games/{id}`)

Problem being addressed:
- Current `crud.get_game()` uses a plain `.first()` lookup with no explicit relationship loading.
- During response serialization, related collections can be lazy-loaded, which can produce extra round trips and tail-latency spikes (observed max ~4s).

Planned change:
- Update `crud.get_game()` to use explicit eager loading (`selectinload`) for relationships required by the game-details response schema.
- Match loading strategy used by `get_games()` where possible to keep behavior consistent.

Expected impact:
- Lower p95/max latency for `GET /api/games/{id}`.
- Fewer latency outliers caused by late lazy loads.
- More predictable response time for game detail dialog opens.

Risk/complexity:
- Low risk, small scope, no API contract change.
- Primary risk is over-eager loading too many relationships; keep to schema-used fields only.

2. Optimize `get_filter_options`

Problem being addressed:
- `crud.get_filter_options()` currently runs multiple `distinct()` queries and returns non-deterministically ordered sets.
- Cold-cache calls are relatively slow (p50 ~536ms, p95 ~780ms, max ~3.4s).
- Non-deterministic ordering can create noisy diffs and reduce practical cache stability across runs.

Planned change:
- Add explicit `order_by(...)` for each filter-options query.
- Keep endpoint-level cache behavior in place, but ensure deterministic output ordering.
- Keep payload shape unchanged.

Expected impact:
- Reduced response-time variance, especially on first fetch after cache miss.
- Stable output ordering for downstream consumers/tests.
- Better UX consistency when the filter dialog initializes.

Risk/complexity:
- Low risk and straightforward.
- Slight potential increase in DB work from ordering, but expected to be offset by cache and improved determinism.

3. Optional follow-up if latency remains high after above changes

Potential next step:
- Introduce a single cache key version stamp tied to catalog/library state for filter options and related metadata endpoints.
- This keeps data fresh after admin/library changes while avoiding unnecessary repeated recomputation.

When to do this:
- Only if post-change profiling still shows unacceptable p95 tail behavior.

## Verification Plan

After changes:
1. Re-run:
```bash
poetry run python scripts/perf/profile_hot_endpoints.py --environment dev --iterations 10
```
2. Compare before/after for:
- `/api/filter-options/` p50/p95/max
- `/api/games/224517` p95/max
3. Keep both JSON artifacts in `logs/profiling/backend_queries/` for traceability.
4. Treat improvement as sufficient if:
- no regressions in endpoint correctness
- max latency outliers are materially reduced
- p95 is directionally improved or stable with fewer spikes
