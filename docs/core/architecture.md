# Architecture

## Current Production Baseline
- Backend: FastAPI (`backend/app`) on Fly.
- Data store: Postgres on Fly (self-managed app model).
- Frontend: React SPA.
- Recommendation runtime uses prebuilt artifacts with degraded-mode behavior when unavailable.

## Environment Strategy
- Separate `dev` and `prod` apps/stacks.
- Promote from validated `dev` SHA to `prod`.
- Keep deploy traceability per release.
- Branch/deploy model:
  - `main` auto-deploys to `dev`.
  - `prod` is promoted manually from a validated SHA.

## Runtime and Operations
- Default runtime profile plus convention-specific runtime mode.
- Health checks and validation scripts are part of deploy acceptance.
- Rollback is release-based and must be reheated with smoke validation.

## Migration/Cutover Principles
- Use explicit cutover steps with rollback path.
- Run migrations conservatively before validation.
- Prefer fix-forward unless tested downgrade path exists.

## API Versioning Policy (Current)
- Pre-`1.0`: single active API surface under `/api` (no parallel `/api/v1` maintenance by default).
- Breaking contract changes are allowed only when frontend + tests + docs are updated in the same release path.
- Introduce formal multi-version API support only if independent external clients require compatibility windows.

## Observability Baseline
- Structured operational logs, health checks, and production validation scripts.
- Alerting path must be functional before high-risk promotions.
- Production alerting is implemented through the scheduled workflow in
  `.github/workflows/prod-health-alerts.yml` backed by
  `scripts/alerts/run_prod_health_alerts.py`.
- Operational controls (enable/disable/manual run) are documented in
  `docs/core/convention_ops.md`.

## Architectural Decision Record Policy
- Durable decisions live in `docs/archive/adr/`.
- Use `docs/active/` for ongoing architecture initiatives.
