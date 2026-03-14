# Documentation Index

This repo organizes docs by lifecycle and audience.

- `installation/`
  - First-time setup and deployment guides.
  - Use this first when bringing up a new local or Fly environment.
  - Includes `migration.md` for environment-to-environment transfer workflows.
- `core/`
  - Evergreen human-readable docs that should remain stable over time.
  - Operational and engineering references you expect to keep long-term.
- `active/`
  - In-progress human-readable docs for current initiatives.
  - Move completed items to `archive/` when done.
- `ai/`
  - AI-oriented docs that improve agent accuracy/speed beyond reading code alone.
  - Keep concise and task-focused.
- `archive/`
  - Historical records retained for context and traceability.
- `deprecated/`
  - Superseded docs scheduled for removal after the next release.

Maintenance rule:
- Prefer updating an existing canonical doc over creating a new file.
- Docs intended for humans should be minimal and task oriented.
