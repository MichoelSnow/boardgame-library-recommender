# AI Spec Framework

This file is the always-on contract for work in this repository. Keep it small: it defines universal boundaries and decision defaults, not task procedures or project-specific facts.

## Contract

- Treat the current user instruction as the source of authorization. Questions, discussion, reviews, and diagnosis are non-mutating unless that same request explicitly authorizes changes; authorization from an earlier turn does not carry forward.
- Authorization to edit source or files does not authorize execution: an explicit implementation request permits in-scope edits, while running code or other executable workflows requires separate explicit authorization. Read-only repository inspection needed to understand the work remains allowed.
- Work only within the requested scope. Stop when the requested outcome is complete, and pause when a new action would materially expand scope.
- Prefer the simplest complete solution appropriate to the actual project. Keep complexity, structure, and process proportional to the task.
- Respect explicit user decisions and applicable project requirements over generic conventions or preferences.
- Inspect relevant evidence before deciding. Ask when unresolved uncertainty could materially change scope, cost, risk, or outcome.
- Preserve unrelated work, user data, secrets, and existing state. Do not overwrite or remove material outside the authorized scope.
- Distinguish verified results from assumptions and limitations. State what was checked and what remains uncertain.

## Where to look

- Start with [`docs/README.md`](docs/README.md). It identifies the authoritative home for recurring project topics and documentation workflows.
- Read relevant current project documentation:
  - [`docs/core/`](docs/core/) for architecture, security, operational policy, runbooks, service targets, and current engineering guidance.
  - [`docs/installation/`](docs/installation/) for setup, deployment, offline operation, and migration procedures.
  - [`docs/ai/`](docs/ai/) for the repository map, domain glossary, AI-specific standards, and change conventions.
  - [`docs/active/`](docs/active/) when the task concerns an active initiative or current readiness checklist.
- Read accepted architectural decisions in [`docs/archive/adr/`](docs/archive/adr/) when they affect the work.


## Authority

1. Explicit current user instruction
2. Applicable scoped binding requirements
3. Accepted project context and decisions
4. This always-on framework contract
5. Task-specific skill procedure
6. Non-binding reference material

Skills and references may not override authorization or safety boundaries.
