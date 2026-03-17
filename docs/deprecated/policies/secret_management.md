# Secret Management and Rotation Policy

## Scope
- Applies to production and development secrets used by `bg_lib_recommender`.
- Applies to secrets stored in:
  - GitHub Actions repository secrets
  - Fly app secrets (`dev` and `prod`)
  - local `.env` files and local shell environment

## Owner
- Owner: repository maintainer (solo developer).

## Baseline Rotation Cadence (Low-Overhead)
- Rotate high-impact secrets every 6 months.
- Rotate lower-impact secrets only on incident, sharing changes, or pre-event hardening.
- Record rotation date and affected secret names in release notes or a short ops log entry.

## Secret Inventory and Storage Locations

### GitHub Repository Secrets (Actions)
- `FLY_API_TOKEN`
  - Used by deploy workflows.
  - Rotate every 6 months.
- `GEMINI_API_KEY`
  - Used by PR-Agent workflow.
  - Rotate every 6 months (or if quota/account issues require regeneration).

### Fly App Secrets (`dev` and `prod`)
- `SECRET_KEY` (required; at least 32 chars)
  - Used for JWT signing and kiosk token signing.
  - Rotate every 6 months.
- `DATABASE_URL`
  - Database credential/connection string.
  - Rotate when DB password rotates (minimum annual or on incident).
- Optional operational secrets in scripts/workflows:
  - `SMOKE_TEST_PASSWORD_DEV`, `SMOKE_TEST_PASSWORD_PROD`
  - `ADMIN_PASSWORD`
  - Rotate every 6 months or when shared/staffing changes.

### Local Development Secrets (`.env` / shell)
- `SECRET_KEY` (use a local-only value, not shared with hosted environments)
- `DATABASE_URL` (if running local Postgres)
- `SMOKE_TEST_PASSWORD_LOCAL`
- `ADMIN_PASSWORD`
- `BGG_PASSWORD` (if used for ingest workflows)
- Rotate on incident, machine compromise, or if shared accidentally.

## Emergency Rotation Triggers
- Rotate immediately if any of the following occurs:
  - secret value is committed, pasted, or exposed publicly
  - credential leak is suspected
  - account/token compromise is suspected

## Emergency Rotation Runbook
1. Generate a new secret with strong entropy (at least 32 characters for `SECRET_KEY`).
2. Update secret values in the deployment environment secret store.
3. Redeploy the application.
4. Verify critical auth flow:
   - `/api/token` returns tokens for valid credentials.
   - protected endpoint `/api/users/me/` works with new token.
5. Invalidate old credentials/tokens where the provider supports explicit revocation.
6. Record incident date, rotated secrets, and confirmation checks.

## How To Rotate by Location

### 1) Rotate GitHub Actions secrets
1. Go to: `GitHub repo -> Settings -> Secrets and variables -> Actions`.
2. Update the relevant secret(s), e.g.:
   - `FLY_API_TOKEN`
   - `GEMINI_API_KEY`
3. Re-run the affected workflow to validate:
   - deploy workflow for `FLY_API_TOKEN`
   - `PR Agent` workflow for `GEMINI_API_KEY`

### 2) Rotate Fly secrets (do `dev` first, then `prod`)
1. Generate a new value.
2. Set in `dev`:
   ```bash
   fly secrets set -a bg-lib-app-dev SECRET_KEY="<new-secret>"
   ```
   Repeat for any other keys being rotated (`DATABASE_URL`).
3. Validate `dev`:
   - `/api/version` responds
   - auth works (`/api/token` + `/api/users/me/`)
   - image paths still resolve after deploy
4. Set the same rotation in `prod`:
   ```bash
   fly secrets set -a bg-lib-app SECRET_KEY="<new-secret>"
   ```
5. Validate `prod` with the same checks.

### 3) Rotate local development secrets
1. Update `.env` values (or shell exports).
2. Restart local app process.
3. Validate local auth/login and any affected script paths.

## Minimal-Maintenance Rotation Checklist
1. Rotate `SECRET_KEY` and `FLY_API_TOKEN` every 6 months.
2. Rotate everything immediately on exposure/suspected compromise.
3. Keep one short log entry per rotation event (date + keys + verification result).

## Notes
- Keep this policy intentionally minimal to reduce maintenance overhead while preserving baseline security hygiene.
