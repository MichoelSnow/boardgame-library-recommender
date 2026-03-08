# Rollback and Deploy Traceability

## Rollback
1. Resolve and verify the rollback target:
```bash
poetry run python scripts/deploy/prepare_fly_rollback.py --env prod
```

2. Identify target release manually if needed:
```bash
fly releases -a <APP_NAME>
```

3. Roll back:
```bash
fly releases rollback <RELEASE_VERSION> -a <APP_NAME>
```

4. Re-run smoke checks:
- `/api`
- `/api/version`
- `/api/games/?limit=1`
- `poetry run python scripts/validate/validate_prod_release.py`

5. If the rollback target predates the currently applied schema, assess whether a downgrade is actually required before attempting one. Default to fixing forward unless you have a tested downgrade path for the affected migrations.

## Release Mapping Record
For each production deploy, record:
1. Git tag or commit SHA
2. Fly release version
3. Deployment timestamp
4. Notes (schema/data migration impact, if any; include whether `alembic upgrade head` was run successfully)

The standard production validation flow now appends this record automatically to:
- `logs/deploy_traceability.jsonl`

## Common Inspection Queries
Use these for quick ad hoc operational checks.

Most recent suggestions in `dev`:
```bash
fly ssh console -a pax-tt-db-dev -C "psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c \"SELECT s.id, u.username, s.comment, s.timestamp FROM user_suggestions s JOIN users u ON u.id = s.user_id ORDER BY s.timestamp DESC LIMIT 20;\""
```
