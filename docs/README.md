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
Use this repository's AGENTS.md and documentation structure as the operating context for this session.

1. Load and follow AGENTS.md.
2. Read docs/README.md to identify the authoritative documentation for the task.
3. Load only the relevant project documentation:
   - docs/core/ for current architecture, policies, operations, and security.
   - docs/installation/ for setup, deployment, or migration work.
   - docs/active/ for current initiatives and unfinished work.
   - docs/archive/adr/ when accepted architectural decisions affect the task.
   - docs/ai/ for repository maps and AI-specific working guidance.
4. Use relevant shared skills (found at ${CODEX_HOME:-$HOME/.codex}/skills/<skill>) when their procedures apply. Use that path exactly.
5. If I explicitly ask to resume from a handoff or session-state file, load and use it. Do not read or update such files automatically.

Before implementation, briefly summarize:
- relevant repository context and documents loaded,
- applicable project requirements or decisions,
- relevant skills,
- any material uncertainty,
- immediate next action.

## Authorization gate

Default mode is strictly read-only.

Do not modify files, dependencies, configuration, databases, generated artifacts, or external state unless the current user message explicitly authorizes that specific change. Do not infer authorization from words such as “address,” “handle,” “resolve,” “take care of,” or “look into.”

Do not run tests, scripts, builds, installs, migrations, deployments, or other executable workflows unless the current user message explicitly authorizes running them. Reading files and performing read-only inspection is allowed when relevant.

If the request could mean either diagnosis/recommendations or implementation, treat it as diagnosis only and stop before changes. Ask for explicit authorization before implementing.

Authorization from prior turns, goals, urgency, or implied intent does not carry forward. Explicit authorization must be present in the current user message.
```
