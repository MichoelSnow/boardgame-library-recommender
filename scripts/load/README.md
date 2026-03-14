# Load Testing Scripts

## `k6_rehearsal.js`

### What it does
- Runs a mixed-load rehearsal against the API.
- Exercises four route classes with configurable traffic weights:
  - `GET /api`
  - `GET /api/version`
  - `POST /api/recommendations`
  - `GET /api/games`
- Tracks custom metrics for recommendation and games latency/error rates.

### When to use it
- Before/after runtime profile changes (workers, timeouts, machine size).
- Before convention windows to verify target load posture.
- After recommendation or `/api/games` query-path changes.

### Prerequisites
- `k6` installed locally.
- Target app is running and reachable.
- For Fly environments with autostop, bring stack up first:
```bash
scripts/deploy/fly_stack.sh dev up
```

### Default behavior
- Base URL: `https://${FLY_APP_NAME_DEV}.fly.dev` (or `BASE_URL` override)
- VUs: `20`
- Duration: `5m`
- Think time: `0.3s`
- Recommendation payload:
  - `library_only=true`
  - `limit=5`
  - random liked-games count from `1` to `50` (bounded by provided `GAME_IDS`)
- Route weights:
  - `WEIGHT_API=0.40`
  - `WEIGHT_VERSION=0.20`
  - `WEIGHT_RECOMMENDATIONS=0.25`
  - `WEIGHT_GAMES=0.15`

### Thresholds enforced by the script
- `http_req_failed: rate<0.02`
- `http_req_duration: p(95)<2500`
- `recommendation_duration: p(95)<4000`
- `recommendation_error_rate: rate<0.02`
- `games_duration: p(95)<2500`
- `games_error_rate: rate<0.02`

### Environment variables
- `BASE_URL`
- `VUS`
- `DURATION`
- `THINK_TIME_SECONDS`
- `GAME_IDS` (CSV)
- `LIKED_MIN`
- `LIKED_MAX`
- `RECOMMENDATION_LIMIT`
- `LIBRARY_ONLY` (`true|false`)
- `WEIGHT_API`
- `WEIGHT_VERSION`
- `WEIGHT_RECOMMENDATIONS`
- `WEIGHT_GAMES`

### Common runs

Mixed profile (recommended baseline):
```bash
k6 run \
  -e BASE_URL="https://${FLY_APP_NAME_DEV}.fly.dev" \
  -e GAME_IDS="224517,167791,174430,173346,266192,161936,13,822,30549,68448" \
  -e LIKED_MIN="1" \
  -e LIKED_MAX="50" \
  -e VUS="10" \
  -e DURATION="3m" \
  -e THINK_TIME_SECONDS="2.0" \
  scripts/load/k6_rehearsal.js
```

Recommendations-only stress:
```bash
k6 run \
  -e BASE_URL="https://${FLY_APP_NAME_DEV}.fly.dev" \
  -e GAME_IDS="224517,167791,174430,173346,266192,161936,13,822,30549,68448" \
  -e LIKED_MIN="1" \
  -e LIKED_MAX="50" \
  -e WEIGHT_API="0" \
  -e WEIGHT_VERSION="0" \
  -e WEIGHT_RECOMMENDATIONS="1" \
  -e WEIGHT_GAMES="0" \
  -e VUS="10" \
  -e DURATION="3m" \
  -e THINK_TIME_SECONDS="2.0" \
  scripts/load/k6_rehearsal.js
```

Games-only stress:
```bash
k6 run \
  -e BASE_URL="https://${FLY_APP_NAME_DEV}.fly.dev" \
  -e WEIGHT_API="0" \
  -e WEIGHT_VERSION="0" \
  -e WEIGHT_RECOMMENDATIONS="0" \
  -e WEIGHT_GAMES="1" \
  -e VUS="10" \
  -e DURATION="3m" \
  -e THINK_TIME_SECONDS="2.0" \
  scripts/load/k6_rehearsal.js
```

### Interpreting results
- Start with threshold pass/fail block.
- For failures, inspect:
  - `http_req_failed`
  - `recommendation_error_rate`
  - `games_error_rate`
  - p95 latency metrics
- Correlate with app logs during the run:
```bash
fly logs -a "${FLY_APP_NAME_DEV}" | rg -n "CRITICAL|WORKER TIMEOUT|ERROR|Out of memory|Killed process"
```
