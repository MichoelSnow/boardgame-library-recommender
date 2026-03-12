# Engineering Guide (V0)

_Last updated: 2025-12-29_

## Purpose
- Single reference for coding standards, testing strategy, and workflow conventions.
- Keep the codebase consistent, readable, and maintainable for future teams.
- Favor simple, explicit code over clever abstractions.
- Treat reliability and privacy as first-class requirements.

## Code Standards
- Prefer small functions with clear names and single responsibility.
- Avoid global state unless intentionally shared.
- Handle edge cases explicitly (empty inputs, missing data, partial failures).
- Remove dead code immediately after refactors.
- Avoid copy-paste divergence across files.
- Use strict typing in TypeScript where feasible; use Python type hints for public APIs.
- Keep domain logic in `services/` or `lib/`, not in UI components.
- Avoid circular imports; dependency flow should be UI -> services -> data.
- For cross-cutting utilities, prefer `packages/shared/` or a dedicated `utils/` module.

## Logging and Errors
- Replace print statements with structured logging.
- Surface user-safe errors in UI; log technical details without PHI.
- Avoid silent fallbacks for critical systems (auth, DB, recommendations); use explicit degraded-mode behavior with clear logs and alerts.

## Testing Strategy
Web Frontend (React)
- Unit/component tests: Jest + React Testing Library.
- API mocking: MSW.
- E2E: Playwright or Cypress for 2-4 critical flows (run on main or nightly).

Recommended web frontend test coverage
- Authentication flow (login, logout, protected routes).
- Filtering and search state behavior.
- Recommendation workflow (liked/disliked games, recommendation refresh/toggle).
- Empty states, loading states, and API error handling.

Backend (FastAPI)
- Unit + API tests: pytest + httpx.
- Schema validation: pydantic models on requests/responses.
- OpenAPI snapshot tests to detect breaking changes.

Recommended backend test coverage
- Invalid inputs and missing required fields.
- Empty results and relevance threshold behavior.
- Partial failures (DB unavailable, timeouts).
- Idempotency/retry behavior for write paths where retries are expected.
- Timeout and error-path behavior for external calls and long-running operations.

Ingestion (Python)
- Unit tests for parsing, normalization, chunking.
- Golden file tests for chunk outputs and citations.
- Manifest validation tests (schema + checksums).

Recommended ingestion test coverage
- Empty inputs and malformed records.
- Citation ID stability and checksum failures.

Security Testing
- Secret scanning (gitleaks) in CI.
- Dependency audits (npm audit, pip audit) in CI.
- PHI checks: ensure no PHI in logs or network payloads.
- Rate limiting must be defined and tested for abuse-prone endpoints.
- Security headers/CSP must be explicitly configured and validated in production builds.
- Every user-facing or externally exposed backend change should include security acceptance criteria in PR review.
- Prefer threat-model-lite review for new public endpoints or major data flow changes.
- Security controls should be testable and ideally automated in CI (not documentation-only).

Security Priority and Context
- High priority defaults: secret hygiene, rate limiting, auth hardening, security headers/CSP, and dependency/supply-chain checks.
- Context-dependent controls:
1. CSRF protections are mandatory when cookie/session auth is used.
2. File upload validation/scanning is mandatory when upload features exist.
3. Network/egress restrictions should be applied where infrastructure supports safe enforcement.

## API and Data Contracts
- Define and document API versioning/deprecation policy, including compatibility windows and sunset communication.
- Define ownership for API/data contracts and require coordinated backend/frontend updates for contract changes.
- Breaking changes must be called out explicitly in release notes.
- Use the canonical release note template and section order in [standards.md](../ai/standards.md).

## CI and Quality Gates
- Lint + format checks on every PR.
- Type checking where applicable.
- Unit tests on every PR.
- E2E on main or nightly.
- Dependency updates monthly via Dependabot; security patches same day.
- Include performance regression checks where thresholds are defined.

## Tooling Documentation and Execution Logging
- Document exact commands for linting, formatting, type checks, and tests (backend and frontend).
- Keep one canonical docs location for these commands and keep it current when tooling changes.
- Ensure CI job names map clearly to command(s) they run.
- Capture and retain quality-check/test outputs in CI logs for traceability.
- For local troubleshooting, document common failures and remediation steps.
- For releases, record that required quality gates passed (or approved exceptions with rationale).
- Record migration/data-change validation outcomes when a release includes schema/data changes.

## Reliability and Operations
- Define backup and restore procedures with periodic restore drills.
- Define RTO/RPO targets and verify them in drills.
- Use migration safety checklists for schema/data changes (backup, validation, rollback criteria).
- Maintain a lightweight incident postmortem process with tracked follow-up actions.
- Include observability impact in PR review when behavior changes (logs/metrics/alerts updated as needed).

## Branching and Workflow
### Goals
- Keep `main` always releasable.
- Encourage short-lived branches with fast review.
- Make CI checks the default gate for merges.

### Branch Types
- `main`: stable, protected, and release-ready.
- `feature/*`: short-lived branches for new work.
- `fix/*`: targeted bugfix branches.
- `chore/*`: tooling and housekeeping changes.

### Workflow
1. Create a branch from `main`.
2. Keep scope small and focused.
3. Open a pull request early for visibility.
4. CI runs on every push and PR.
5. Merge to `main` after review and green checks.

### Merge Policy
- Prefer squash merges to keep history clean.
- Require CI checks before merge.
- Avoid merging broken tests.

### Naming Conventions
- Use a clear, descriptive suffix: `feature/ai-opt-in-toggle`.
- Include a ticket ID if one exists.

## Documentation Expectations
- Update docs when behavior or data flows change.
- Log major architectural decisions in the decision log.
