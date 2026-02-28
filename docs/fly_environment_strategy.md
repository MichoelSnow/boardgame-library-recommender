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

Notes:
- `SECRET_KEY` is required at startup and must be at least 32 characters.
- Use a different `SECRET_KEY` for `local`, `dev`, and `prod`.
- `CORS_ALLOWED_ORIGINS` is optional if the default Fly hostnames are unchanged.
- If Fly hostnames or custom domains change, update `CORS_ALLOWED_ORIGINS` or the backend defaults before deploy.

## Branch to Environment Mapping
- `main` -> auto-deploy to `dev` (GitHub workflow: `.github/workflows/fly-deploy.yml`)
- `prod` -> manual promotion after validation (GitHub workflow: `.github/workflows/fly-deploy-prod.yml`)
- feature/fix/chore branches -> CI only by default; optional manual dev deploy when needed

## Promotion Flow
1. Merge to `main`.
2. GitHub Actions auto-deploys `main` to `dev`.
3. Run smoke checks on `dev`:
   - `/api`
   - `/api/version`
   - `/api/games/?limit=1`
4. Confirm recommendation/embedding health behavior.
5. Run the `Fly Deploy Prod` workflow to promote the validated ref to `prod`.
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
  - environment-specific secrets/allowed CORS origins

## Region Strategy
- Current strategy: single region (`iad`) for both environments.
- Rationale: lowest operational complexity while traffic/latency needs remain moderate.
- Reassess multi-region only if latency/SLA goals require it.

## Resource Baseline
- `prod`: `shared-cpu-4x`
- `dev`: `shared-cpu-4x`

## Scaling Triggers (Reassessment Thresholds)
- Increase `prod` VM size if sustained p95 latency exceeds target for 3 consecutive days.
- Increase `prod` capacity if CPU saturation or memory pressure causes restarts/timeouts.
- Keep `dev` at parity with `prod` unless cost or test requirements justify an intentional divergence.

## CORS Policy by Environment
- `prod`: explicit origins only (no wildcard + credentials).
- `dev`: explicit localhost origins plus explicit dev URL as needed.
- Source of truth: `CORS_ALLOWED_ORIGINS` env var (comma-separated).
- Current backend defaults allow the Fly `prod` and `dev` hostnames if `CORS_ALLOWED_ORIGINS` is unset.
