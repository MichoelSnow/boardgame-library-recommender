# Postgres Migration Plan

## Purpose
- Define the execution plan for migrating `pax_tt_recommender` from SQLite-on-Fly-volume to self-managed Postgres on Fly.
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

## Current Status
- `DATABASE_URL` support with SQLite fallback is implemented in shared app/Alembic configuration.
- Initial Postgres compatibility audit is complete:
  - no blocking SQLite-only assumptions were found in runtime SQLAlchemy models
  - current Alembic revisions and the post-import SQL script are expected to translate to Postgres
  - `backend/tests/create_indexes.py` remains SQLite-specific, but it is test-only and not part of runtime cutover
- The root Alembic revision now bootstraps an empty database to the post-`d258c28b421e` base schema so the historical migration chain can be replayed on a fresh Postgres instance.
- Native local Postgres inside WSL is running and validated.
- `poetry run alembic upgrade head` succeeds on a fresh local Postgres database.
- The app starts successfully against the fresh local Postgres schema and responds on:
  - `/api`
  - `/api/version`
- The one-time SQLite -> Postgres migration utility now exists at:
  - `backend/scripts/migrate_sqlite_to_postgres.py`
- The utility has focused unit coverage for table-ordering, batching, and legacy `pax_games` normalization edge cases.
- The utility has been run successfully end-to-end against local Postgres:
  - row-count parity is verified table-by-table during migration
  - local source-data anomalies in `pax_games.bgg_id` are normalized to `NULL` when they do not map to a valid `games.id`
  - a warning summary is emitted when those `pax_games.bgg_id` anomalies are normalized during migration
- The self-managed `dev` Postgres Fly app is provisioned and reachable.
- `poetry run alembic upgrade head` succeeds against `dev` Postgres from the deployed app container.
- The current `dev` SQLite dataset has been migrated successfully into `dev` Postgres.
- The Postgres-backed `dev` environment has passed:
  - release validation against the deployed branch SHA
  - Fly health checks
  - auth smoke test
  - recommendation artifact validation
  - recommendation endpoint validation
  - performance gate validation
- The self-managed Postgres backup procedure has been tested successfully against `dev`.
- The self-managed Postgres restore procedure has been tested successfully against a disposable `dev` restore database.
- The self-managed `prod` Postgres Fly app is provisioned and reachable.
- `poetry run alembic upgrade head` and the one-time SQLite -> Postgres migration path have been executed for `prod`.
- `pax-tt-app` is cut over to `pax-tt-db-prod` via `DATABASE_URL`.
- Production release validation passed on the cutover release (release `v40`), with health checks, auth flow, recommendation checks, performance gate, and rollback target confirmation.
- SQLite pre-cutover backup was retained through production validation and can be removed after post-cutover stabilization window per runbook.
- Remaining items in this document are still execution tasks and should remain staged behind local-first validation.

## Required Sequence
1. Add `DATABASE_URL` support with SQLite fallback in application config.
2. Audit code and migrations for SQLite-specific assumptions.
3. Stand up native local Postgres inside WSL.
4. Run Alembic against local Postgres.
5. Build and validate the SQLite -> Postgres data migration path locally.
6. Provision self-managed Postgres on Fly for `dev`.
7. Run Alembic on `dev` Postgres.
8. Migrate `dev` data and cut `dev` over to Postgres.
9. Validate and stabilize `dev`.
10. Provision self-managed Postgres on Fly for `prod`.
11. Run Alembic on `prod` Postgres.
12. Migrate `prod` data and cut `prod` over to Postgres.
13. Validate `prod`.
14. Keep SQLite available as the short-term rollback path during stabilization.

## Architecture Decisions
- Stay inside Fly infrastructure where reasonably possible.
- Use self-managed Postgres on Fly for both `dev` and `prod`.
- Keep `dev` and `prod` data fully isolated.
- Require local Postgres validation before any Fly cutover.
- For this environment, use native Postgres inside WSL as the local proving ground.
- Keep recommendation artifacts on local mounted storage during the first Postgres migration step.
- Treat convention worker-count and machine-memory tuning as a separate runtime decision validated by rehearsal, not as part of the DB cutover itself.
- Prefer self-managed Postgres on Fly over managed Fly Postgres because the managed service's fixed monthly cost is too high for the current budget.
- Accept the operational tradeoff of self-management in exchange for materially lower monthly cost.
- Treat backup, restore, and DB health monitoring as required parts of this migration, not optional follow-up work.

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
- For Fly self-managed Postgres with DB autostop/autostart enabled, use the Flycast hostname in `DATABASE_URL`:
  - `postgresql://<user>:<password>@<db-app>.flycast:5432/<db>`
- Avoid relying on `<db-app>.internal` for this mode because name resolution/startup can fail when the DB machine is stopped.
- Flycast requires a private IP allocation on the DB app before hostname resolution works:
  - `fly ips allocate-v6 --private -a <db-app>`
- Keep DB apps private-only and verify no public IPs are attached:
  - `fly ips list -a <db-app>`

## Dev Cutover
1. Provision a self-managed Postgres Fly app for `dev`.
2. Allocate Flycast private IP for `pax-tt-db-dev` if missing:
```bash
fly ips list -a pax-tt-db-dev
fly ips allocate-v6 --private -a pax-tt-db-dev
```
3. Verify DB networking posture is private-only:
```bash
fly ips list -a pax-tt-db-dev
```
4. Set `DATABASE_URL` for `pax-tt-app-dev` (Flycast host recommended for autostop mode).
5. Run:
```bash
fly ssh console -a pax-tt-app-dev -C 'sh -lc "cd /app/backend && poetry run alembic upgrade head"'
```
6. Load migrated data into `dev` Postgres.
7. Deploy/cut the `dev` app over to Postgres.
8. Run the standard dev validation flow:
```bash
poetry run python scripts/validate_dev_deploy.py
```
9. Perform targeted manual regression checks for DB-backed behavior.

## Prod Cutover
1. Provision a self-managed Postgres Fly app for `prod`.
2. Allocate Flycast private IP for `pax-tt-db-prod` if missing:
```bash
fly ips list -a pax-tt-db-prod
fly ips allocate-v6 --private -a pax-tt-db-prod
```
3. Verify DB networking posture is private-only:
```bash
fly ips list -a pax-tt-db-prod
```
4. Set `DATABASE_URL` for `pax-tt-app` (Flycast host recommended for autostop mode).
5. Run:
```bash
fly ssh console -a pax-tt-app -C 'sh -lc "cd /app/backend && poetry run alembic upgrade head"'
```
6. Load migrated data into `prod` Postgres.
7. Deploy/cut the `prod` app over to Postgres.
8. Run the standard prod validation flow:
```bash
poetry run python scripts/validate_prod_release.py
```
9. Keep the legacy SQLite DB intact until the Postgres-backed release is proven stable.

## Existing DB App + New Fly Config Adoption
When a DB app already exists and you are moving to `fly.db.dev.toml` or `fly.db.prod.toml`, avoid accidental duplicate machine/volume resources.

1. Inspect current resources:
```bash
fly machines list -a <db-app>
fly volumes list -a <db-app>
```
2. Keep one intended data volume and remove unintended duplicates before cutover.
3. For deterministic re-attachment to an existing volume (only during no-traffic windows):
   - stop dependent app stack first
   - destroy old DB machine (volume remains)
   - ensure only intended volume remains
   - deploy with the DB Fly config
4. Re-verify one DB machine + intended volume + private Flycast IP before reconnecting app traffic.

## Rollback Strategy
- Initial rollback should be configuration rollback back to the preserved SQLite-backed deployment path.
- Do not assume a safe Postgres -> SQLite reverse migration exists.
- Default to:
  - switch app config back to SQLite
  - redeploy the last known-good SQLite-backed release
- Only consider DB downgrade paths after they are explicitly tested.
- Treat this rollback as a service-recovery path, not a zero-loss bidirectional data-reconciliation path.

## Self-Managed Operations Requirements
- Define and document the self-managed Postgres app/container configuration for both `dev` and `prod`.
- Define and test a backup procedure before the production cutover.
- Define and test a restore procedure before convention launch.
- Add DB-health monitoring and alerting to the observability stack.
- Treat backup/restore validation as a launch requirement, not an optional hardening task.

## Backup Procedure
- The initial backup method is a logical SQL dump created with:
  - `pg_dump`
  - executed over `fly ssh console`
  - written to a local file on the operator machine
- The repeatable local command is:

```bash
poetry run python scripts/fly_postgres_backup.py --env dev
poetry run python scripts/fly_postgres_backup.py --env prod --output /tmp/pax-tt-prod-before-cutover.sql
```

- The backup task is not complete until:
  - the script runs successfully against the target Fly Postgres app
  - the resulting `.sql` file is non-empty
  - the output file is retained long enough for the planned change window

## Restore Procedure
- The initial restore-validation method is:
  - recreate a disposable test database on the Fly Postgres app
  - pipe the local SQL dump into `psql`
  - verify the restored database contains public tables
- The repeatable local command is:

```bash
poetry run python scripts/fly_postgres_restore.py --env dev --input /tmp/pax-tt-dev-postgres-backup-20260304T012020Z.sql
poetry run python scripts/fly_postgres_restore.py --env prod --input /tmp/pax-tt-prod-before-cutover.sql --restore-db pax_tt_recommender_restore_test
```

- The restore task is not complete until:
  - the script runs successfully against the target Fly Postgres app
  - the disposable restore database is created successfully
  - restore verification confirms the restored database contains public tables

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
- Define exact local Postgres setup commands for WSL in the long-term runbook if they need to be repeatable on a new machine.
- Add standalone verification scripts or reports if you want table-parity checks outside the migration run itself.

## Local Development After Migration
- During the migration, local development may remain dual-mode:
  - `DATABASE_URL` preferred
  - SQLite fallback available
- After Postgres is stable in production, local development should move to Postgres-first by default.
- SQLite fallback should be treated as transitional, not permanent technical debt.
- Before the final `prod` Postgres cutover, production should fail fast if `DATABASE_URL` is missing instead of silently falling back to SQLite.

## Exit Criteria
- Local Postgres validation passes.
- The SQLite -> Postgres migration utility runs successfully against local Postgres and preserves row counts/IDs.
- `dev` is running on self-managed Postgres on Fly and passes all automated/manual validation.
- `prod` is running on self-managed Postgres on Fly and passes all automated/manual validation.
- The Postgres-backed deployment supports the agreed Phase 4 non-functional targets.
- Backup and restore procedures are documented and have been tested successfully.
- SQLite fallback is retained until the new production path is stable enough to retire it deliberately.

## Local Data Migration Command
After bootstrapping the local Postgres schema, run:

```bash
export DATABASE_URL="postgresql://${POSTGRES_USER}:${LOCAL_POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB}"
poetry run python backend/scripts/migrate_sqlite_to_postgres.py
```

This command expects:
- source SQLite database at the default local app path
- target Postgres schema already created via `poetry run alembic upgrade head`
- an empty target Postgres database
