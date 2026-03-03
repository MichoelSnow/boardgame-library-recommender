# Postgres Migration Plan

## Purpose
- Define the execution plan for migrating `pax_tt_recommender` from SQLite-on-Fly-volume to Fly Postgres.
- Reduce operational risk by validating locally first, then cutting over `dev`, then `prod`.
- Keep the relational database migration separate from later image-storage and other infrastructure changes.

## Service-Level Reference
- Canonical performance, reliability, recovery, and data-loss targets are defined in [service_level_targets.md](/home/msnow/git/pax_tt_recommender/docs/policies/service_level_targets.md).
- This migration is only complete when the Postgres-backed deployment can support those targets.

## Cutover Strategy Reference
- Cross-cutting sequencing and rollback rules are defined in [migration_cutover_strategy.md](/home/msnow/git/pax_tt_recommender/docs/architecture/migration_cutover_strategy.md).
- This migration must follow the isolated-cutover rule and preserve the SQLite fallback path during stabilization.

## Scope
- Migrate application relational data from SQLite to Postgres.
- Keep recommendation artifacts (`.npz`, `.json`) on the Fly volume during this migration.
- Keep image-storage migration out of scope for this document.
- Keep the initial backend runtime strategy separate from the DB cutover:
  - recommendation artifacts stay volume-backed
  - convention worker-count tuning is validated by rehearsal before final runtime adjustments

## Non-Goals
- Do not migrate recommendation artifacts into Postgres.
- Do not combine this migration with the image-storage move.
- Do not remove the SQLite fallback path until Postgres-backed production is stable.

## Required Sequence
1. Add `DATABASE_URL` support with SQLite fallback in application config.
2. Audit code and migrations for SQLite-specific assumptions.
3. Stand up native local Postgres inside WSL.
4. Run Alembic against local Postgres.
5. Build and validate the SQLite -> Postgres data migration path locally.
6. Provision Fly Postgres for `dev`.
7. Run Alembic on `dev` Postgres.
8. Migrate `dev` data and cut `dev` over to Postgres.
9. Validate and stabilize `dev`.
10. Provision Fly Postgres for `prod`.
11. Run Alembic on `prod` Postgres.
12. Migrate `prod` data and cut `prod` over to Postgres.
13. Validate `prod`.
14. Keep SQLite available as the short-term rollback path during stabilization.

## Architecture Decisions
- Stay inside Fly infrastructure where reasonably possible.
- Use Fly Postgres for both `dev` and `prod`.
- Keep `dev` and `prod` data fully isolated.
- Require local Postgres validation before any Fly cutover.
- For this environment, use native Postgres inside WSL as the local proving ground.
- Keep recommendation artifacts on local mounted storage during the first Postgres migration step.
- Treat convention worker-count and machine-memory tuning as a separate runtime decision validated by rehearsal, not as part of the DB cutover itself.

## Local Validation (WSL)
### Goals
- Prove the app can run against Postgres before touching Fly.
- Catch SQL dialect, migration, and query-behavior issues quickly.

### Local Setup Requirements
- Native Postgres installed inside the WSL environment.
- A local Postgres database dedicated to this project.
- `DATABASE_URL` configured for local app execution.

### Recommended Local Setup Model
- Use native Postgres installed directly inside WSL.
- Prefer the default local service on `localhost:5432`.
- Create a dedicated database and user for this project.
- Use an explicit `DATABASE_URL` such as:
  - `postgresql://<user>:<password>@localhost:5432/pax_tt_recommender`

### Local Validation Checklist
1. Start local Postgres in WSL.
2. Set local `DATABASE_URL`.
3. Run:
```bash
cd backend
poetry run alembic upgrade head
cd ..
```
4. Execute the SQLite -> Postgres migration path locally.
5. Start the app locally against Postgres.
6. Verify:
- auth still works
- filtering still works
- recommendations still work
- writes still work
- IDs and relationships are intact

## Data Migration Requirements
- Preserve primary keys exactly.
- Preserve foreign-key relationships exactly.
- Migrate users without changing password hashes.
- Migrate data in dependency order.
- Verify row counts table-by-table after migration.
- Log and report any row mismatches before cutover.

## Configuration Contract
- Application database configuration should use the following precedence:
  1. if `DATABASE_URL` is set, use it directly
  2. otherwise fall back to SQLite via `DATABASE_PATH`
- This dual-mode contract is the intended transition path during the migration.

## Dev Cutover
1. Provision Fly Postgres for `dev`.
2. Set `DATABASE_URL` for `pax-tt-app-dev`.
3. Run:
```bash
fly ssh console -a pax-tt-app-dev -C 'sh -lc "cd /app/backend && poetry run alembic upgrade head"'
```
4. Load migrated data into `dev` Postgres.
5. Deploy/cut the `dev` app over to Postgres.
6. Run the standard dev validation flow:
```bash
poetry run python scripts/validate_dev_deploy.py
```
7. Perform targeted manual regression checks for DB-backed behavior.

## Prod Cutover
1. Provision Fly Postgres for `prod`.
2. Set `DATABASE_URL` for `pax-tt-app`.
3. Run:
```bash
fly ssh console -a pax-tt-app -C 'sh -lc "cd /app/backend && poetry run alembic upgrade head"'
```
4. Load migrated data into `prod` Postgres.
5. Deploy/cut the `prod` app over to Postgres.
6. Run the standard prod validation flow:
```bash
poetry run python scripts/validate_prod_release.py
```
7. Keep the legacy SQLite DB intact until the Postgres-backed release is proven stable.

## Rollback Strategy
- Initial rollback should be configuration rollback back to the preserved SQLite-backed deployment path.
- Do not assume a safe Postgres -> SQLite reverse migration exists.
- Default to:
  - switch app config back to SQLite
  - redeploy the last known-good SQLite-backed release
- Only consider DB downgrade paths after they are explicitly tested.
- Treat this rollback as a service-recovery path, not a zero-loss bidirectional data-reconciliation path.

## Migration Script Recommendation
- Build a dedicated one-time migration utility under `backend/scripts/` or `scripts/`.
- Use SQLAlchemy sessions for both:
  - source SQLite
  - target Postgres
- Migrate table-by-table in dependency order.
- Preserve primary keys explicitly.
- Do not rely on raw SQL dump translation.

## Parity Verification Recommendation
- Verify row counts for every table after migration.
- Add targeted spot checks for critical entities and relationships, including:
  - users
  - games
  - mechanics/categories relationships
  - `pax_games`
- Verify auth/login behavior after migration.
- Prefer a scriptable verification report where possible.

## Open Implementation Work
- Add `DATABASE_URL` support with SQLite fallback.
- Build the one-time SQLite -> Postgres migration utility.
- Define exact local Postgres setup commands for WSL.
- Audit Alembic revisions and raw SQL for Postgres compatibility.
- Add verification scripts or checks for row-count parity after migration.

## Local Development After Migration
- During the migration, local development may remain dual-mode:
  - `DATABASE_URL` preferred
  - SQLite fallback available
- After Postgres is stable in production, local development should move to Postgres-first by default.
- SQLite fallback should be treated as transitional, not permanent technical debt.

## Exit Criteria
- Local Postgres validation passes.
- `dev` is running on Fly Postgres and passes all automated/manual validation.
- `prod` is running on Fly Postgres and passes all automated/manual validation.
- The Postgres-backed deployment supports the agreed Phase 4 non-functional targets.
- SQLite fallback is retained until the new production path is stable enough to retire it deliberately.
