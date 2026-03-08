# Deploy Policy and Preconditions

## Purpose
- Standardize deployment and rollback for the Fly `dev` and `prod` apps.
- Ensure each release is traceable to git commit + Fly release.

## Deployment Policy
- Pull requests and feature branches run CI only.
- Pushes to `main` auto-deploy to the Fly `dev` app via GitHub Actions.
- Production deploys are manual promotions using the `Fly Deploy Prod` GitHub Actions workflow after `dev` smoke checks pass.

## Versioning Policy
- Do not bump the app version on every commit or every `dev` deploy.
- Use `git_sha` and `build_timestamp` for commit-level traceability on `dev`.
- Bump the app version only for intentional `prod` releases.
- Every new `prod` deploy should increase the release version by at least one increment.
- The canonical app version source is `pyproject.toml`.

### Increment Rules
- Patch (`0.1.0` -> `0.1.1`):
  - bug fixes
  - deploy/ops hardening
  - security fixes without major user-facing workflow change
  - refactors or cleanup that are shipped to `prod`
- Minor (`0.1.0` -> `0.2.0`):
  - user-visible features
  - meaningful API additions or behavior changes
  - architecture changes that alter runtime behavior or operational expectations
  - breaking changes while still pre-`1.0`
- Major (`0.x` -> `1.0.0`):
  - only when the app is considered stable enough for a true release-ready baseline

### When To Bump
1. Finish the code for the release milestone.
2. Validate the release on `dev`.
3. Decide the next semantic version.
4. Update `pyproject.toml`.
5. Promote that exact validated SHA to `prod`.
6. Create or update the matching Git tag after the promotion succeeds.

### Tagging Rule
- Use one semantic-version tag format for production releases.
- Recommended format:
  - `prod-v0.1.1`
- Fly release versions (`v37`, etc.) are infrastructure release IDs, not app versions.

### Release Notes Rule
- Use the canonical release notes format in:
  - [release_notes_standard.md](/home/msnow/git/pax_tt_recommender/docs/policies/release_notes_standard.md)
- Keep section headers and order consistent across releases.
- Publish notes for each production tag (`prod-vX.Y.Z`) using that template.

## Preconditions
- `flyctl` authenticated.
- Correct app selected (`dev` or `prod`).
- Required secrets are already set in Fly.
- For Postgres-backed environments with DB autostop enabled, `DATABASE_URL` should use Flycast hostnames (for example `pax-tt-db-dev.flycast`), not `.internal` hostnames.
- Flycast private IP is allocated on each DB app used by the app:
  - `fly ips list -a pax-tt-db-dev`
  - `fly ips list -a pax-tt-db-prod`
  - If missing, allocate it:
    - `fly ips allocate-v6 --private -a pax-tt-db-dev`
    - `fly ips allocate-v6 --private -a pax-tt-db-prod`
- DB apps should remain private-only. Verify there are no public IPs:
  - `fly ips list -a pax-tt-db-dev`
  - `fly ips list -a pax-tt-db-prod`
- Treat database migrations as required on every deploy, even if a given commit appears not to change schema. This is the conservative default for this project.
- Local development also requires `.env` with `SECRET_KEY` (minimum 32 characters) before the backend will start.
- Optional but recommended for full auth smoke coverage: set environment-specific smoke-test credentials in local `.env`:
  - shared username: `SMOKE_TEST_USERNAME`
  - env-specific passwords:
    - `SMOKE_TEST_PASSWORD_LOCAL`
    - `SMOKE_TEST_PASSWORD_DEV`
    - `SMOKE_TEST_PASSWORD_PROD`
- If you want to create or recreate the smoke-test user via script, also set:
  - `ADMIN_USERNAME`
  - `ADMIN_PASSWORD`
