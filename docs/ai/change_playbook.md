# AI Change Playbook

## Before Editing
1. Identify canonical code path and owning tests.
2. Confirm target docs under `docs/core` or `docs/active`.
3. Avoid editing archived/deprecated docs except migration moves.

## During Editing
1. Keep changes small and single-purpose.
2. Remove dead code from prior iterations.
3. Add/adjust tests for behavioral changes.
4. Keep logs sanitized (no secrets/tokens/passwords).

## Schema Change Checklist
1. Update SQLAlchemy models in `backend/app/models.py`.
2. Create migration with Alembic.
3. Apply migration locally and validate key flows.
4. Update import scripts if schema/data loading assumptions changed.
5. Update API schemas/tests impacted by the model change.

## Validation
- Run targeted tests for changed modules first.
- Run project quality gates (`ruff`, selected pytest) before finalizing.
- Ensure links/doc references point to canonical locations.

## Commit Hygiene
- Group related code + test + doc updates together.
- Prefer clear commit messages that state behavior impact.
