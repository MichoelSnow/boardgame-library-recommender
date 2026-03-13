# Service Level Targets

## Purpose
- Define the canonical performance, reliability, and recovery targets for `bg_lib_recommender`.
- Provide a single source of truth for Phase 4 architecture decisions and later operational validation.

## Scope
- These targets apply to the convention-use production path unless a narrower scope is stated explicitly.
- Planning docs and runbooks should reference this file instead of restating the same thresholds.

## Latency Targets
- Catalog, search, and game-list endpoints:
  - target p95 latency under `1000 ms`
- Recommendation endpoints:
  - target p95 latency under `2500 ms`
- Image delivery:
  - target first meaningful image visible under `1500 ms` on representative convention Wi-Fi/mobile conditions

## Reliability Target
- Overall application error rate:
  - target under `1%` during convention hours

## Recovery Targets
- Service-impacting incidents:
  - acknowledge within `5 minutes`
- Primary app path:
  - recover within `15 minutes`

## Data Loss Tolerance
- Committed writes:
  - no loss beyond the last successful transaction
- Monthly rebuild intermediates:
  - treated as reproducible
  - they do not define the primary recovery point objective

## Definitions
- `Primary app path`:
  - the core user-facing flow for browsing/searching games, viewing game details, and loading recommendations
- `Convention hours`:
  - the active convention runtime window defined in [convention_runtime_policy.md](/home/msnow/git/bg_lib_recommender/docs/architecture/convention_runtime_policy.md)

## Usage
- Architecture and migration plans should state how their implementation supports these targets.
- Operational alert thresholds may be stricter or more specific, but should remain aligned with these targets.
- The observability and alerting implementation should use these targets as the baseline for alert thresholds and escalation.
