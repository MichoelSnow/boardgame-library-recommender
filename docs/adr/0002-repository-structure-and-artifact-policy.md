# ADR 0002: Repository Structure and Artifact Policy

## Status
- Accepted (2026-03-07)

## Context
- The repository has grown across backend runtime, frontend UI, data pipeline, and operations workflows.
- Phase 5 requires stable layout boundaries and explicit artifact hygiene rules.

## Decision
- Keep the existing top-level directories with explicit ownership boundaries:
  - `backend/`, `frontend/`, `data_pipeline/`, `scripts/`, `docs/`, `data/`, `logs/`
- Rename the prior `crawler/` directory to `data_pipeline/` and keep `data_pipeline/` as the canonical name.
- Formalize file placement and artifact policy in:
  - `docs/policies/repository_structure_policy.md`
- Enforce backup/temp artifact hygiene through:
  - `.gitignore` patterns (`*.bak`, `*.tmp`, `*.orig`)
  - removal of tracked backup artifacts from source control
- Require notebook inventory and keep/convert decisions in `data_pipeline/README.md`.

## Consequences
- Clearer placement rules reduce accidental sprawl and improve onboarding.
- Existing scripts/docs can reference stable ownership boundaries.
- Path references needed one-time updates across docs/workflows and were completed as part of the rename.
