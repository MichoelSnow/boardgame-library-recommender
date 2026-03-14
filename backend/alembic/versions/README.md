# Alembic Versioning Policy

This directory currently contains two classes of revisions:

1. Legacy revision chain (retained for compatibility/history)
2. Post-baseline revisions (new work going forward)

## Baseline Decision

- Canonical schema source: old production Postgres schema exported to `.tmp/canonical_prod_schema.sql`
- Fresh-install bootstrap path: apply canonical schema, then `alembic stamp head`
- Do not replay legacy revisions for fresh installs

## Legacy Revisions (Archive Candidates)

The following revisions are retained temporarily and marked as archive candidates:

- `d258c28b421e`
- `163d675a5e9d`
- `69941843136f`
- `2ef6c56d7dc0`
- `ed8c617c6e84`
- `6d4ea4dc16c2`
- `594a7422f114`
- `7091f7e4de89`
- `4f77595d6dba`
- `1a2b3c4d5e6f`

## Archive Gate

Archive/squash these legacy revisions only after all are true:

1. At least one new post-baseline revision exists.
2. Fresh-install baseline bootstrap is validated in dev and prod.
3. Existing-DB upgrade path is validated once on a non-production copy.

Until then, keep legacy files in this directory so Alembic revision resolution remains intact.
