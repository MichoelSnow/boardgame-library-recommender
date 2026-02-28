# Best Practices Migration Guide: `pax_tt_recommender` (V1)

_Last updated: 2026-02-27_

## Purpose
- Provide a step-by-step checklist to move `pax_tt_recommender` from "working prototype" to "reliable production web app."
- Apply the general engineering guide to this repo's stack and deployment model.
- Prioritize correctness, observability, and deploy safety before deep refactors.

## Scope
1. Backend API (`backend/app`)
2. Frontend SPA (`frontend/src`)
3. Data ingestion/recommendation pipeline (`crawler/src`, import scripts)
4. Deployment and ops on Fly.io

## Current Baseline
- Known-good tag/release mapping exists:
  - Git tag: `prod-v0.1`
  - Fly release: `v34`
- Current semantic app version baseline should be treated as:
  - `0.1.0`
- Local repo may contain additional unpushed dependency updates; this guide assumes work proceeds from the tagged baseline plus new planned changes.
- [x] [P0] Known-good production baseline tag exists (`prod-v0.1`).
- [x] [P0] Baseline Fly release mapping is recorded (`v34`).

## Release Increment Policy
- Do not bump the app version on every commit.
- `dev` deploys should normally keep the same app version and rely on `git_sha` + `build_timestamp` for traceability.
- Every intentional `prod` release should bump the app version by at least one increment.
- Before `1.0.0`, treat:
  - patch bumps as internal hardening and bug-fix releases
  - minor bumps as the correct place for breaking changes or meaningful user-visible capability changes

### Recommended Phase-to-Version Mapping
- Phases 0-3:
  - default release type: patch
  - rationale: release hygiene, environment setup, contract correctness, promotion safety
  - example: `0.1.0` -> `0.1.1`
- Phase 4:
  - default release type: no bump for docs-only evaluation
  - bump to minor only if you ship a real architecture/runtime decision to `prod`
  - example: `0.1.1` -> `0.2.0`
- Phase 5:
  - default release type: patch
  - rationale: repo structure and naming cleanup should not usually change user-facing behavior
- Phase 6:
  - default release type: no bump for test-only work
  - patch if bug fixes are bundled into the release that goes to `prod`
- Phase 7:
  - default release type: patch
  - rationale: security hardening should produce a distinct production release, even if user-visible behavior is mostly unchanged
- Phase 8:
  - default release type: no bump for CI-only work
  - patch only if user-facing or runtime behavior changes ship with it
- Phase 9:
  - default release type: patch
  - rationale: toolchain/runtime modernization changes deployment/runtime expectations even if features do not change

### Version Bump Timing
1. Complete the milestone you intend to ship.
2. Validate the candidate in `dev`.
3. Decide the next version number.
4. Update the version in the repo.
5. Promote that exact validated SHA to `prod`.
6. Tag the production release with the matching semantic version.

## Project-Specific Risks to Address
- Schema/model naming drift in some backend CRUD paths.
- At least one frontend/backend field mismatch (`minimum_age` vs `min_age`).
- Recommender startup dependency on embedding artifacts needs explicit failure policy.
- No explicit API version/commit endpoint for runtime traceability.
- CI quality gates appear partial/inconsistent across backend/frontend/security.

## Ordered Execution Checklist
Priority legend:
- `P0`: must complete before next production release.
- `P1`: important; complete in current migration cycle.
- `P2`: valuable but deferrable; complete after core stabilization.

Execution rule:
- Minimum phase completion: all `P0` items in the phase are done.
- Full phase completion: all `P0` + `P1` items are done (`P2` may defer if explicitly tracked).

### Phase 0: Release Hygiene and Traceability (1-2 days)
- [x] [P1] Add Docker build arg `GIT_SHA`.
- [x] [P1] Set runtime env var `APP_GIT_SHA` from build arg.
- [x] [P0] Add `/api/version` endpoint returning commit SHA, build timestamp, app version, and environment.
- [x] [P0] Add deploy/rollback runbook in `docs/` with smoke-test commands.
- [x] [P1] Add release map entry format in changelog (`tag <-> commit <-> fly release`).
- [x] [P0] Verify on deployed app that `/api/version` returns expected SHA.
- [x] [P1] Add/standardize GitHub Actions CI workflow file(s) (`.github/workflows/ci.yml` or equivalent).
- [x] [P1] Configure PR-Agent (AI code review) integration and document usage/guardrails.

### Phase 1: Environment Strategy (Dev vs Prod) (1-2 days)
- [x] [P0] Define two Fly environments/apps: `dev` and `prod`.
- [x] [P0] Define separate persistent data volumes for `dev` and `prod`.
- [x] [P0] Define separate env var sets/secrets for `dev` and `prod`.
- [x] [P1] Document branch-to-environment deployment mapping.
- [x] [P0] Document promotion flow: deploy to `dev`, validate, then promote to `prod`.
- [x] [P0] Document emergency rollback flow for `prod` and verification steps post-rollback.
- [x] [P1] Define Fly config parity policy (`fly.toml` templates for dev/prod; only intentional differences allowed).
- [x] [P2] Document Fly region strategy (single-region vs multi-region) and rationale.
- [x] [P1] Define Fly resource sizing baseline (CPU/RAM/concurrency) for each environment.
- [x] [P2] Define scaling trigger thresholds and runbook for resizing.
- [x] [P0] Define strict CORS policy per environment (explicit allowed origins; no wildcard+credentials in production).

### Phase 2: Contract Correctness (3-5 days)
- [x] [P1] Audit backend models/schemas/crud for naming mismatches and broken paths.
- [x] [P0] Fix known backend path mismatches (including CRUD helper fields).
- [x] [P1] Audit frontend field usage against backend schema.
- [x] [P0] Fix known frontend mismatch (`minimum_age` -> `min_age`) and similar issues.
- [x] [P1] Add explicit API validation for query params and sort fields.
- [x] [P1] Decide recommender artifact policy (fail-fast or degraded mode).
- [x] [P0] Implement chosen policy with explicit logs and API behavior.
- [x] [P0] Add `pytest` to the project dev toolchain/environment and verify it runs locally.
- [x] [P0] Add tests for the chosen policy.
- [x] [P0] Define degraded-mode API response contract for recommendation endpoints.
- [x] [P1] Centralize local file-based logs under the root `logs/` directory and remove scattered log outputs from source directories.
- [x] [P1] Define frontend degraded-state UX copy and behavior when recommendations are unavailable.

### Phase 3: Promotion Gates (Pre-Prod Validation) (1-2 days)
- [x] [P1] Define required checks before prod promotion.
- [x] [P1] API smoke tests.
- [x] [P1] Auth flow smoke tests.
- [x] [P1] Recommendation endpoint health check.
- [x] [P0] Embedding file integrity/existence check in target environment.
- [x] [P1] Define pass/fail criteria and who can approve promotion (you).
- [x] [P1] Add checklist template for each promotion event.
- [x] [P1] Add performance regression gate (baseline latency/error thresholds) before prod promotion.
- [x] [P1] Define Fly deploy strategy and document when to use it.
- [ ] [P0] Verify Fly health checks pass before marking deploy successful.
- [x] [P1] Record deploy traceability on each promotion (git SHA, Fly release version, migration/version marker).
- [x] [P1] Make the app read its semantic version from one canonical source so release bumps happen in one place.
- [x] [P0] Document and test Fly rollback command path for failed promotions.

### Phase 4: Architecture and Tooling Reassessment (3-6 days)
- [ ] [P1] Document current and expected usage profile:
- [ ] [P1] concurrent users (avg and peak)
- [ ] [P1] recommendation request volume
- [ ] [P1] data ingestion/update frequency
- [ ] [P1] uptime expectations and tolerated downtime
- [ ] [P1] Define target non-functional requirements:
- [ ] [P1] response-time targets (p95)
- [ ] [P1] reliability target
- [ ] [P1] recovery objectives (RTO/RPO)
- [ ] [P1] Evaluate DB technology fit (SQLite on Fly volume vs managed Postgres) against requirements.
- [ ] [P1] Evaluate separate environments for dev/prod:
- [ ] [P1] same DB technology across envs vs mixed setup
- [ ] [P1] data isolation strategy
- [ ] [P1] migration and rollback complexity
- [ ] [P1] Evaluate backend/runtime fit:
- [ ] [P1] FastAPI deployment model and worker strategy
- [ ] [P1] model artifact loading strategy and storage location
- [ ] [P1] Evaluate frontend architecture fit:
- [ ] [P1] API layer organization
- [ ] [P1] caching/query invalidation strategy
- [ ] [P1] Evaluate observability and alerting tooling fit:
- [ ] [P1] log aggregation approach
- [ ] [P1] email alert channel and escalation workflow
- [ ] [P2] Define API versioning and deprecation policy (compatibility window + sunset process).
- [ ] [P1] Define data contract ownership (backend schema owner and frontend integration responsibilities).
- [ ] [P2] Record decisions in ADRs with options considered, tradeoffs, and final decision.
- [ ] [P1] Create a concrete migration plan for any chosen architecture changes (sequencing, cutover, rollback).
- [ ] [P1] Get explicit go/no-go sign-off before implementing architecture changes.

### Phase 5: Repository Structure and Naming Cleanup (2-5 days)
- [ ] [P1] Define target top-level layout and ownership for `backend/`, `frontend/`, pipeline code, scripts, data, and docs.
- [ ] [P2] Decide whether `crawler/` should be renamed to a clearer name (for example `pipeline/` or `data_pipeline/`).
- [ ] [P1] Decide final location boundaries:
- [ ] [P1] runtime/import scripts that currently live in `backend/app/`
- [ ] [P1] pipeline scripts vs exploratory notebooks
- [ ] [P1] test utilities vs production scripts
- [ ] [P1] generated artifacts vs source-controlled files
- [ ] [P1] Add a file-placement policy:
- [ ] [P1] no generated build outputs committed unless explicitly required
- [ ] [P1] no runtime logs/DB/model artifacts in source directories
- [ ] [P1] no backup files (for example `*.bak`) in production code paths
- [ ] [P1] Audit and remove/relocate obsolete or duplicate files (for example duplicate test/performance scripts).
- [ ] [P1] Add/update `.gitignore` rules to match artifact policy.
- [ ] [P0] Remove tracked backup/temp artifacts from source control and prevent reintroduction (for example `*.bak` checks).
- [ ] [P1] Define notebook policy:
- [ ] [P1] where notebooks live
- [ ] [P1] whether notebook data/secrets are allowed in repo
- [ ] [P1] Review all existing notebooks and document:
- [ ] [P1] what feature/workflow value each notebook adds
- [ ] [P1] whether each notebook should remain a notebook or be converted into a script/module
- [ ] [P1] ownership and maintenance expectations for notebooks kept in repo
- [ ] [P1] conversion plan for notebook logic that should move to scripts
- [ ] [P0] Run credential-artifact hygiene pass (notebooks/scripts) and remove blocked files (tokens/keys/secrets).
- [ ] [P0] Add pre-commit/CI check to block committing known secret artifact patterns.
- [ ] [P1] Add or update README coverage:
- [ ] [P1] `backend/README.md` (API, migrations, local run/test)
- [ ] [P1] `frontend/README.md` (dev server, build, test, env vars)
- [ ] [P1] pipeline directory README (data flow, commands, outputs)
- [ ] [P1] `scripts/README.md` (what each script does and when to run it)
- [ ] [P1] `docs/README.md` index linking key guides and runbooks
- [ ] [P1] Update root `README.md` project structure section to reflect final layout.
- [ ] [P1] Record major structure decisions in ADRs.

### Phase 6: Testing Foundation (4-7 days)
- [ ] [P0] Add backend API tests for `/api/games` filtering/pagination/sort.
- [ ] [P0] Add backend API tests for `/api/recommendations` and `/api/recommendations/{id}`.
- [ ] [P0] Add backend API tests for auth endpoints (`/api/token`, `/api/users/me`, password change).
- [ ] [P1] Add backend API tests for suggestions endpoint.
- [ ] [P0] Add backend edge-case tests (invalid params, unauthenticated access, empty results).
- [ ] [P1] Add OpenAPI contract snapshot test.
- [ ] [P1] Add frontend integration tests (auth flow, filtering, recommendation flow, API error states).
- [ ] [P1] Add MSW-based API mocks for deterministic frontend tests.
- [ ] [P1] Add crawler/pipeline unit tests for `data_processor.py` and `create_embeddings.py`.
- [ ] [P1] Add fixture/golden tests for output shape and key fields.
- [ ] [P0] Ensure all tests run in CI on PR.
- [ ] [P1] Document test commands for backend, frontend, and pipeline in repo docs.
- [ ] [P1] Document expected test runtime and minimum local prerequisites.
- [ ] [P1] Add load/performance baseline tests and store reference results.
- [ ] [P1] Define performance regression thresholds and failure policy.

### Phase 7: Security Hardening (2-4 days)
- [x] [P0] Remove insecure production fallback behavior for `SECRET_KEY`.
- [x] [P0] Make production startup fail if required security env vars are missing.
- [x] [P1] Add `gitleaks` to CI.
- [ ] [P1] Add Python dependency audit (`pip-audit` or equivalent) to CI.
- [ ] [P1] Add npm dependency audit policy to CI.
- [ ] [P1] Add auth behavior tests for token expiry and unauthorized response consistency.
- [ ] [P1] Review and scrub logs for sensitive data exposure.
- [ ] [P1] Define outbound email alert channel for production incidents.
- [ ] [P1] Define alert recipients and escalation path.
- [ ] [P1] Document how to run security scans locally and in CI.
- [ ] [P0] Implement endpoint rate limiting policy (auth endpoints, recommendation endpoints, and general API).
- [ ] [P1] Validate rate-limit behavior with abuse and load test scenarios.
- [ ] [P0] Add security headers baseline (at minimum: HSTS, CSP, `X-Content-Type-Options`, and frame protections).
- [ ] [P0] Validate CSP in production mode and document allowed origins/resources.
- [ ] [P0] Define secret management and rotation policy (owner, cadence, emergency rotation runbook).
- [ ] [P1] Verify encryption controls (TLS in transit; storage encryption expectations at rest).
- [ ] [P2] Add SBOM generation in CI and store SBOM artifact per build.
- [ ] [P1] Add lightweight threat-model checklist for new public endpoints/features.
- [ ] [P0] Require security acceptance criteria in PRs for user-facing/backend-exposed changes.
- [ ] [P0] Ensure security controls have corresponding automated tests where feasible.
- [ ] [P0] Define data retention and minimization policy for app, logs, and pipeline outputs.
- [ ] [P2] Define bot protection policy (for example Turnstile/CAPTCHA) for abuse-prone forms/endpoints.
- [ ] [P2] If file uploads are introduced: add upload validation and malware-scanning requirements before release.
- [ ] [P2] If cookie-based auth is introduced: add CSRF protection requirements and tests before release.
- [ ] [P2] If infrastructure supports it: define network policy and egress restrictions by environment.
- [ ] [P0] Add automated security-misconfiguration tests (for example fail if insecure auth/CORS settings are used in production config).

### Phase 8: CI/CD and Quality Gates (2-4 days)
- [ ] [P0] Standardize Python formatting/linting (`black`, `ruff`).
- [ ] [P0] Standardize frontend formatting/linting (`eslint`, `prettier`).
- [ ] [P2] Add Python type checks (`mypy`) for critical backend modules.
- [ ] [P0] Add required status checks in branch protection for `main`.
- [ ] [P0] Enforce merge blocking on failed lint/tests/security checks.
- [ ] [P1] Add dependency update cadence (scheduled PRs + patch SLA).
- [ ] [P0] Re-enable `python-quality` CI job and require it to pass.
- [ ] [P0] Re-enable `frontend-build` CI job and require it to pass.
- [ ] [P1] Re-enable `frontend-audit` CI job with agreed vulnerability policy (baseline/allowlist/threshold).
- [ ] [P0] Make Python CI tests deterministic by creating a CI test DB fixture/setup step (no silent test skips allowed).
- [ ] [P1] Add a `Quality Commands` section in docs with exact local commands:
- [ ] [P1] Python format/lint/fix commands (`black`, `ruff`).
- [ ] [P1] Frontend format/lint commands (`prettier`, `eslint`).
- [ ] [P1] Type-check commands (`mypy` and frontend type checks if enabled).
- [ ] [P1] Add CI mapping in docs (which command runs in which CI job).
- [ ] [P1] Add troubleshooting notes for common quality-check failures.

### Phase 9: Toolchain Modernization (Poetry + Python) (2-4 days)
- [ ] [P1] Upgrade project tooling to Poetry `2.3.x`.
- [ ] [P1] Update team/dev setup docs to install and use Poetry `2.3.x`.
- [ ] [P1] Update CI and deploy workflows to use Poetry `2.3.x`.
- [ ] [P1] Run dependency compatibility audit for Python `3.13`.
- [ ] [P1] If all dependencies pass on Python `3.13`, set project target to Python `3.13`.
- [ ] [P1] If any critical dependency fails on Python `3.13`, set target to Python `3.12` and document blockers.
- [ ] [P1] Update `pyproject.toml` Python constraint to selected target version.
- [ ] [P1] Regenerate lockfile under the selected Python target.
- [ ] [P1] Run full backend, frontend, and pipeline test suite on selected Python target in CI.
- [ ] [P1] Add rollback note for toolchain migration (previous Poetry/Python baseline and restore steps).
- [ ] [P1] Update setup docs with exact Poetry and Python install/verification commands.
- [ ] [P0] Add startup config validation for required env vars and value ranges.

### Phase 10: Observability and Operational Readiness (2-4 days)
- [ ] [P1] Add structured logs with request IDs.
- [ ] [P1] Add request timing middleware (endpoint + method + status + duration).
- [ ] [P0] Add `/health/live` endpoint.
- [ ] [P0] Add `/health/ready` endpoint with DB/model readiness checks.
- [ ] [P1] Define and document 5xx rate target.
- [ ] [P1] Define and document p95 latency target.
- [ ] [P1] Define and document auth failure alert threshold.
- [ ] [P1] Document incident triage steps in runbook.
- [ ] [P0] Add production alert for missing/corrupt embeddings.
- [ ] [P0] Ensure alert sends email and includes environment, release SHA, and failure reason.
- [ ] [P1] Add periodic embedding health check and alert on transition to degraded mode.
- [ ] [P1] Validate alert noise controls (dedupe/rate limit) to avoid spam.
- [ ] [P1] Add incident postmortem template and follow-up tracking process.
- [ ] [P1] Add release-note template that flags breaking changes and deprecations.
- [ ] [P1] Document Fly operational diagnostics runbook (`fly status`, `fly releases`, machine status, and log inspection).
- [ ] [P2] Define Fly cost guardrails (budget threshold and monthly review process).
- [ ] [P2] Define alert path for unexpected Fly cost/resource growth.

### Phase 11: Architecture Cleanup and Performance (ongoing)
- [ ] [P1] Move heavy business logic from FastAPI handlers into service modules.
- [ ] [P1] Centralize frontend API calls in a dedicated service layer.
- [ ] [P1] Profile and optimize hot queries and N+1 patterns.
- [ ] [P1] Revisit cache strategy and invalidation rules.
- [ ] [P2] Add lightweight ADRs for major architecture decisions.
- [ ] [P1] Define idempotency and retry strategy for write endpoints and ingestion jobs.
- [ ] [P1] Define timeout/retry policy for external calls and long-running jobs.

### Phase 12: Data Safety and Migration Discipline (2-4 days)
- [ ] [P0] Define backup cadence and retention policy for production data.
- [ ] [P1] Implement and document backup verification checks.
- [ ] [P0] Run and document restore drills to validate RTO/RPO targets.
- [ ] [P1] Define DB migration checklist:
- [ ] [P1] pre-migration backup
- [ ] [P1] reversible migration expectation (or documented exception)
- [ ] [P1] post-migration validation and rollback decision point
- [ ] [P0] Include migration safety checklist in every production deployment that changes schema/data.
- [ ] [P1] Define Fly volume backup/snapshot procedure and schedule.
- [ ] [P0] Validate restore from Fly backup/snapshot in a drill.
- [ ] [P1] Document data migration procedure between Fly volumes/apps.
- [ ] [P2] Run Fly disaster recovery drill (machine/volume failure simulation) and record recovery outcomes.

## Recommended Order
1. Phase 0
2. Phase 1
3. Phase 2
4. Phase 3
5. Phase 4
6. Phase 5
7. Phase 6
8. Phase 7
9. Phase 8
10. Phase 9
11. Phase 10
12. Phase 11
13. Phase 12

## Definition of Done: "Best Practices Baseline"
- [x] [P1] Runtime release metadata available via `/api/version`.
- [ ] [P1] CI enforces lint, tests, and security checks on every PR.
- [ ] [P1] Core backend and frontend flows have regression coverage.
- [ ] [P1] Deploy/rollback runbook exists and has been exercised.
- [ ] [P1] Known schema/contract mismatches are resolved.
- [x] [P1] Dev and prod environments are separated and documented.
- [ ] [P1] Promotion to prod requires passing pre-prod validation checklist.
- [ ] [P1] Production supports degraded recommendation mode with email alerts for embedding failures.
- [ ] [P1] Toolchain is modernized to Poetry `2.3.x` and latest compatible Python target (`3.13` preferred, `3.12` fallback).
- [ ] [P1] Architecture/tooling ADRs are completed and any selected architecture migrations are planned with rollback.
- [ ] [P1] Repository structure, naming, and README coverage are standardized and documented.
- [ ] [P1] Security hardening controls are implemented with documented exceptions for context-dependent items.
- [ ] [P1] Data backup/restore and migration safety processes are documented and exercised.

## Security Priority and Context Notes
1. `High priority now`:
- rate limiting, security headers/CSP, secret rotation policy, data retention/minimization, and security acceptance criteria with test coverage.
2. `Should follow soon`:
- bot protection on abuse-prone endpoints and SBOM/supply-chain controls.
3. `Context-dependent (implement when context applies)`:
- CSRF protections when cookie/session auth is used (current token strategy may reduce immediate need).
- file upload security controls when upload features exist.
- stricter network/egress controls when infrastructure supports granular policy without breaking required integrations.

## Decision Log Needed (Before Full Execution)
- [ ] [P1] Database strategy decision: continue SQLite volume long-term, or plan move to managed Postgres.
- [ ] [P1] Embedding failure policy decision: fail startup or degrade recommendation features.
- [ ] [P1] CI strictness timing decision: enforce required checks immediately or after Phase 2 stabilization.
- [ ] [P1] Frontend typing decision: stay JS-first or begin incremental TypeScript for new modules.
- [ ] [P1] Python target decision after compatibility audit: Python `3.13` or Python `3.12`.
- [ ] [P1] Database decision after reassessment: keep SQLite (with guardrails) or migrate to Postgres.

## Appendix: Future Improvements (Nice to Have)
1. Multi-region Fly rollout strategy (if latency/availability goals require it).
2. Incremental TypeScript migration plan for frontend modules.
3. Advanced network egress restriction policy beyond baseline controls.
4. Supply-chain hardening beyond baseline SBOM (for example signing/attestation).
5. Cost optimization playbook beyond guardrails (periodic right-sizing and storage optimization).
