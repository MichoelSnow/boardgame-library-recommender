# Database Scripts

## `fly_postgres_backup.py`
- What it does:
  - Runs `pg_dump` over `fly ssh console` and writes a local SQL dump.
- When to use:
  - Before cutovers, before risky schema operations, or for backup drills.
- How to use:
```bash
poetry run python scripts/db/fly_postgres_backup.py --env dev
poetry run python scripts/db/fly_postgres_backup.py --env prod --output /tmp/pax-tt-prod-backup.sql
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
  --input /tmp/pax-tt-dev-backup.sql
```
