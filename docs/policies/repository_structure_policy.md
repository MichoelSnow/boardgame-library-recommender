# Repository Structure Policy

## Purpose
- Define stable top-level repository layout and ownership boundaries.
- Keep production/runtime code, pipeline code, and operational tooling clearly separated.
- Prevent generated/runtime artifacts from drifting into source-controlled paths.

## Top-Level Layout and Ownership
- `backend/`
  - FastAPI runtime application, models, migrations, runtime profile, and backend tests.
  - Owner: backend/runtime.
- `frontend/`
  - React application source and frontend tests/build config.
  - Owner: frontend.
- `data_pipeline/`
  - Data collection and embedding pipeline code plus exploratory notebooks.
  - Owner: data/pipeline.
- `scripts/`
  - Deploy/validation/ops scripts used from local or CI.
  - Owner: platform/ops.
- `docs/`
  - Policies, architecture plans, roadmaps, runbooks, ADRs.
  - Owner: repository-wide.
- `data/`
  - Local-only pipeline outputs and intermediate datasets.
  - Not source-controlled.
- `logs/`
  - Local operational logs and traceability outputs.
  - Not source-controlled (except README guidance).

## Naming Decision: `data_pipeline/`
- Keep the directory name `data_pipeline/`.
- Rationale:
  - the directory now covers ingest, transform, feature generation, and asset workflows.
  - `data_pipeline` is clearer than `crawler` for the full scope of responsibilities.
  - no ambiguity with runtime backend/frontend domains.

## Location Boundaries
- Runtime/import logic for the backend stays under `backend/app/`.
- Pipeline execution code stays under `data_pipeline/src/`.
- Exploratory analysis stays under `data_pipeline/notebooks/`.
- Test utilities remain under `backend/tests/` and `data_pipeline/tests/`; production scripts remain under `scripts/`.
- Generated artifacts must not be committed in source code paths.

## File Placement Rules
- Do not commit generated build outputs unless explicitly required.
  - Example: `frontend/build/` should not be committed.
- Do not store runtime logs, database files, or model artifacts in source directories.
- Do not keep backup/temp files in production code paths (`*.bak`, `*.tmp`, `*.orig`).
- Store durable docs in `docs/` only; avoid duplicated policy fragments in ad-hoc files.

## Notebook Policy
- Notebooks live only in `data_pipeline/notebooks/`.
- Secrets/tokens/credentials must never be stored in notebooks.
- Notebook output should not contain secret-bearing payloads.
- Notebook logic that becomes production workflow must be migrated into `data_pipeline/src/` modules/scripts.

## Existing Notebook Review Rule
- Each notebook kept in repo must have:
  - purpose/value statement
  - owner
  - keep-as-notebook vs convert-to-script decision
- The canonical inventory is maintained in `data_pipeline/README.md`.

## Artifact Hygiene Enforcement
- `.gitignore` must include backup/temp artifact patterns (`*.bak`, `*.tmp`, `*.orig`).
- CI secret scanning (`gitleaks`) is required and acts as a blocking guardrail for known secret artifacts.
