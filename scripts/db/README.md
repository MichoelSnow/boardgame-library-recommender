# Database Scripts

## `fly_postgres_backup.py`
- What it does:
  - Runs `pg_dump` over `fly ssh console` and writes a local SQL dump.
- When to use:
  - Before cutovers, before risky schema operations, or for backup drills.
- How to use:
```bash
poetry run python scripts/db/fly_postgres_backup.py --env dev
poetry run python scripts/db/fly_postgres_backup.py --env prod --output /tmp/bg-lib-prod-backup.sql
```

## `fly_postgres_restore.py`
- What it does:
  - Restores a SQL dump into a disposable restore-test DB on Fly and verifies table presence.
- When to use:
  - Backup/restore drill validation.
- How to use:
```bash
poetry run python scripts/db/fly_postgres_restore.py \
  --env dev \
  --input /tmp/bg-lib-dev-backup.sql
```

## `bootstrap_fly_postgres_baseline.py`
- What it does:
  - Applies a canonical schema SQL file to Fly Postgres and stamps Alembic to `head`.
- When to use:
  - Fresh Fly installs where you want canonical baseline schema instead of replaying legacy migrations.
- How to use:
```bash
poetry run python scripts/db/bootstrap_fly_postgres_baseline.py \
  --env dev \
  --schema-file .tmp/canonical_repo_schema.sql \
  --reset-db
```

## `transform_canonical_schema.py`
- What it does:
  - Rewrites legacy canonical schema naming (`pax_games`) to current repo naming (`library_games`).
- When to use:
  - Before baseline bootstrap when source schema comes from old prod dump.
- How to use:
```bash
poetry run python scripts/db/transform_canonical_schema.py \
  --input .tmp/canonical_prod_schema.sql \
  --output .tmp/canonical_repo_schema.sql
```
