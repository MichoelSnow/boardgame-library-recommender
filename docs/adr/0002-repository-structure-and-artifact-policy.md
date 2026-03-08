# ADR 0002: Repository Structure and Artifact Policy

## Status
- Accepted (2026-03-07)

## Context
- The repository has grown across backend runtime, frontend UI, data pipeline, and operations workflows.
- Phase 5 requires stable layout boundaries and explicit artifact hygiene rules.

## Decision
- Keep the existing top-level directories with explicit ownership boundaries:
  - `backend/`, `frontend/`, `crawler/`, `scripts/`, `docs/`, `data/`, `logs/`
- Keep the pipeline directory name as `crawler/` for now.
- Formalize file placement and artifact policy in:
  - `docs/policies/repository_structure_policy.md`
- Enforce backup/temp artifact hygiene through:
  - `.gitignore` patterns (`*.bak`, `*.tmp`, `*.orig`)
  - removal of tracked backup artifacts from source control
- Require notebook inventory and keep/convert decisions in `crawler/README.md`.

## Consequences
- Clearer placement rules reduce accidental sprawl and improve onboarding.
- Existing scripts/docs can reference stable ownership boundaries.
- Future rename of `crawler/` remains possible, but is explicitly deferred until value outweighs churn.
