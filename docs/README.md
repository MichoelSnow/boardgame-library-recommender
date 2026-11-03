# Documentation Index

Start here when you are unsure which document or command to use. This index is
navigation only; the linked documents are authoritative for their topics.

## Choose a task

| If you want to... | Start here |
| --- | --- |
| Install or deploy the application for the first time | [Installation and deployment](installation/deployment.md) |
| Refresh BoardGameGeek data | [Data pipeline guide](../data_pipeline/README.md) |
| Operate the dedicated Fly ingest machine | [Fly ingest commands](../scripts/ingest/README.md) |
| Process ingest artifacts or build recommendation files | [Data pipeline guide](../data_pipeline/README.md) |
| Import processed data into a local database | [Data pipeline guide](../data_pipeline/README.md#3a-import-into-a-local-database) |
| Import processed data into deployed Fly Postgres | [Data pipeline guide](../data_pipeline/README.md#3b-import-into-deployed-fly-postgres) |
| Deploy, validate, promote, or roll back the application | [Core runbook](core/runbook.md) |
| Find a command without reading a workflow | [Command reference](core/command_reference.md) |
| Understand architecture or operational policy | [Core documentation](core/README.md) |

## Data refresh at a glance

The data workflow has three distinct phases. The choices in each phase are not
all commands to run:

1. **Collect data**: choose local collection or remote Fly collection.
2. **Process artifacts**: run the local transformations and feature builders
   needed by the destination and runtime features.
3. **Import data**: choose a local database import or a remote Fly Postgres
   import. Library import and database reset are optional operations.

The [data pipeline guide](../data_pipeline/README.md) explains the choices and
prerequisites. The [Fly ingest commands](../scripts/ingest/README.md) document
the ingest machine interface itself.

## Source of truth

This matrix identifies the canonical home for recurring topics. Other docs
should link to these sections rather than duplicate their procedures.

| Topic | Authoritative document | Other docs |
| --- | --- | --- |
| First-time setup and deployment | `docs/installation/deployment.md` | Link only |
| Data collection, processing, and import choices | `data_pipeline/README.md` | Link only |
| Fly ingest machine operations | `scripts/ingest/README.md` | Link only |
| Individual pipeline script behavior | `scripts/data_pipeline/README.md` | Link only |
| Application deployment, promotion, rollback, and validation | `docs/core/runbook.md` | Link only |
| Short command lookup | `docs/core/command_reference.md` | Link only |
| Architecture and long-lived policies | `docs/core/*.md` | Link only |

## Documentation lifecycle

- `installation/`
  - First-time setup and deployment guides.
  - Use this first when bringing up a new local or Fly environment.
  - Includes `migration.md` for environment-to-environment transfer workflows.
  - Includes `local_offline_kiosk_guide.md` for Windows local-host fallback during internet outages.
- `core/`
  - Evergreen human-readable docs that should remain stable over time.
  - Operational and engineering references you expect to keep long-term.
- `active/`
  - In-progress human-readable docs for current initiatives.
  - Move completed items to `docs/archive/` when done.
- `ai/`
  - AI-oriented docs that improve agent accuracy/speed beyond reading code alone.
  - Keep concise and task-focused.
- `archive/`
  - Historical records retained for context and traceability.

Maintenance rule:
- Prefer updating an existing canonical doc over creating a new file.
- Docs intended for humans should be minimal and task oriented.


## Session Start Prompt

Use this at the start of a session when you want the agent to explicitly establish project context before working:

```text
Use this repository's framework as the operating context for this session.

1. Load and follow AGENTS.md.
2. Read docs/project_context.md if project characteristics are relevant to the current task.
3. Identify and load any applicable scoped requirements under docs/requirements/.
4. If I explicitly ask to resume from a handoff/session-state file, load and use that file. Do not read or update session-state files automatically.
5. Use relevant shared skills for task-specific procedures.
6. Treat docs/reference/ as non-binding guidance unless an applicable scoped requirement explicitly adopts it.

Before implementation, briefly summarize:
- framework/context loaded,
- applicable scoped requirements,
- relevant skills,
- any material uncertainty,
- immediate next action.

Do not modify files until the current request explicitly authorizes implementation.
```
