# Fly Environment Strategy (Phase 1)

## Environments
- `prod`: app `pax-tt-app` using `fly.toml`
- `dev`: app `pax-tt-app-dev` using `fly.dev.toml`

## Persistent Volumes
- `prod`: volume `boardgames_data` mounted at `/data`
- `dev`: volume `boardgames_data_dev` mounted at `/data`

## Secrets and Env Sets
Set each environment independently:
- `SECRET_KEY`
- `CORS_ALLOWED_ORIGINS`
- `DATABASE_PATH` (in config file, `/data/boardgames.db`)
- any provider/API credentials required for optional integrations

## Branch to Environment Mapping
- `main` -> deploy to `prod` (GitHub workflow: `.github/workflows/fly-deploy.yml`)
- feature/fix/chore branches -> deploy manually to `dev` for validation

## Promotion Flow
1. Deploy branch/commit to `dev`.
2. Run smoke checks on `dev`:
   - `/api`
   - `/api/version`
   - `/api/games/?limit=1`
3. Confirm recommendation/embedding health behavior.
4. Merge to `main`.
5. CI deploys `main` to `prod`.
6. Run the same smoke checks in `prod`.

## Emergency Rollback (Prod)
1. Identify last healthy release:
```bash
fly releases -a pax-tt-app
```
2. Roll back:
```bash
fly releases rollback <RELEASE_VERSION> -a pax-tt-app
```
3. Re-run smoke checks.

## Config Parity Policy
- Keep `fly.toml` and `fly.dev.toml` structurally aligned.
- Allowed differences:
  - `app` name
  - volume source name
  - VM size
  - environment-specific secrets/allowed CORS origins

## Region Strategy
- Current strategy: single region (`iad`) for both environments.
- Rationale: lowest operational complexity while traffic/latency needs remain moderate.
- Reassess multi-region only if latency/SLA goals require it.

## Resource Baseline
- `prod`: `shared-cpu-4x`
- `dev`: `shared-cpu-2x`

## Scaling Triggers (Reassessment Thresholds)
- Increase `prod` VM size if sustained p95 latency exceeds target for 3 consecutive days.
- Increase `prod` capacity if CPU saturation or memory pressure causes restarts/timeouts.
- Keep `dev` smaller unless test workloads require higher resources.

## CORS Policy by Environment
- `prod`: explicit origins only (no wildcard + credentials).
- `dev`: explicit localhost origins plus explicit dev URL as needed.
- Source of truth: `CORS_ALLOWED_ORIGINS` env var (comma-separated).
