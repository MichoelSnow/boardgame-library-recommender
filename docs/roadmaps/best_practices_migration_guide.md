# Best Practices Migration Guide: `pax_tt_recommender` (V1)

_Last updated: 2026-02-27_

## Purpose
- Provide a step-by-step checklist to move `pax_tt_recommender` from "working prototype" to "reliable production web app."
- Apply the general engineering guide to this repo's stack and deployment model.
- Prioritize correctness, observability, and deploy safety before deep refactors.

## Scope
1. Backend API (`backend/app`)
2. Frontend SPA (`frontend/src`)
3. Data ingestion/recommendation pipeline (`data_pipeline/src`, import scripts)
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

Deployment verification rule:
- For phases that include checks requiring a live Fly deployment, treat the phase PR/commit as implementation completion.
- Final verification for those deploy-dependent items happens only after merge to `main`, automatic `dev` deployment, and successful post-merge validation against the deployed app.
- Do not create a second "phase completion" commit just to satisfy deploy-time verification unless that validation uncovers a real bug that requires a code or config change.

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
- [x] [P0] Run `alembic upgrade head` in the target environment on every dev and prod deploy before treating the deploy as valid.
- [x] [P1] Define pass/fail criteria and who can approve promotion (you).
- [x] [P1] Add checklist template for each promotion event.
- [x] [P1] Add performance regression gate (baseline latency/error thresholds) before prod promotion.
- [x] [P1] Define Fly deploy strategy and document when to use it.
- [x] [P0] Verify Fly health checks pass before marking deploy successful.
- [x] [P1] Record deploy traceability on each promotion (git SHA, Fly release version, migration/version marker).
- [x] [P1] Make the app read its semantic version from one canonical source so release bumps happen in one place.
- [x] [P0] Document and test Fly rollback command path for failed promotions.

### Phase 4A: Architecture and Tooling Decisions (3-6 days)
- [x] [P1] Document current and expected usage profile:
- [x] [P1] concurrent users (peak: ~100 short term during convention, ~5000 medium term; mostly reads with a small number of concurrent writes)
- [x] [P1] recommendation request volume
- [x] [P1] data ingestion/update frequency
- [x] [P1] uptime expectations and tolerated downtime
- [x] [P1] Define target non-functional requirements:
- [x] [P1] response-time targets (p95)
- [x] [P1] reliability target
- [x] [P1] recovery objectives (RTO/RPO)
- [x] [P1] Evaluate DB technology fit (SQLite on Fly volume vs managed Postgres) against requirements.
- [x] [P1] Evaluate separate environments for dev/prod:
- [x] [P1] same DB technology across envs vs mixed setup
- [x] [P1] data isolation strategy
- [x] [P1] migration and rollback complexity
- [x] [P1] Evaluate backend/runtime fit:
- [x] [P1] FastAPI deployment model and worker strategy
- [x] [P1] model artifact loading strategy and storage location
- [x] [P1] Define and require a convention-condition rehearsal/load-test phase before locking worker count and machine sizing.
- [x] [P1] Evaluate frontend architecture fit:
- [x] [P1] API layer organization
- [x] [P1] caching/query invalidation strategy
- [x] [P1] Evaluate observability and alerting tooling fit:
- [x] [P1] log aggregation approach
- [x] [P1] alert channel and escalation workflow
- [x] [P2] Define API versioning and deprecation policy (compatibility window + sunset process).
- [x] [P1] Define data contract ownership (backend schema owner and frontend integration responsibilities).
- [x] [P2] Record decisions in ADRs with options considered, tradeoffs, and final decision.
- [x] [P1] Create a concrete migration plan for any chosen architecture changes (sequencing, cutover, rollback).
- [x] [P1] Get explicit go/no-go sign-off before implementing architecture changes.
- [x] [P1] Create dedicated planning docs for:
- [x] [P1] Postgres migration (`docs/architecture/postgres_migration_plan.md`)
- [x] [P1] convention-mode access (`docs/architecture/convention_mode_access_plan.md`)
- [x] [P1] image storage migration (`docs/architecture/image_storage_migration_plan.md`)
- [x] [P1] convention runtime policy (`docs/architecture/convention_runtime_policy.md`)
- [x] [P1] observability and alerting (`docs/architecture/observability_alerting_plan.md`)
- [x] [P1] frontend architecture (`docs/architecture/frontend_architecture_plan.md`)
- [x] [P1] migration cutover strategy (`docs/architecture/migration_cutover_strategy.md`)
- [x] [P1] data contract ownership (`docs/policies/data_contract_ownership.md`)
- [x] [P1] Select and finalize the primary image-storage runtime path for Phase 4 implementation (Fly-local with R2 backup retained).

### Phase 4B: Architecture Implementation (Must Occur Before Later Phases)
- [x] [P1] Implement `DATABASE_URL` support with SQLite fallback.
- [x] [P1] Complete the Postgres compatibility audit.
- [x] [P1] Stand up native local Postgres inside WSL and validate local app startup against Postgres.
- [x] [P1] Run `alembic upgrade head` against local Postgres and verify schema creation succeeds.
- [x] [P1] Build and test a one-time SQLite -> Postgres migration path locally, preserving IDs and relationship integrity.
- [x] [P1] Provision self-managed Postgres on Fly for `dev`, migrate schema/data, and cut `dev` over to Postgres.
- [x] [P1] Run the full dev validation flow on Postgres-backed `dev` and stabilize any regressions.
- [x] [P1] Provision self-managed Postgres on Fly for `prod`, migrate schema/data, and cut `prod` over to Postgres.
- [x] [P1] Keep the SQLite fallback path intact until Postgres-backed `prod` is validated and stable.
- [x] [P1] Record final Postgres cutover and rollback decisions in `docs/architecture/postgres_migration_plan.md`.
- [x] [P1] Define and test backup and restore procedures for self-managed Postgres on Fly before the production cutover.
- [x] [P1] Update the app image to include `backend/scripts/` so deploy-environment operational scripts are available inside the container.
- [x] [P1] Before the final Postgres `prod` cutover, make production fail fast when `DATABASE_URL` is missing instead of silently falling back to SQLite.
- [x] [P1] Implement the minimum observability stack required before risky cutovers:
- [x] [P1] periodic production health-check/alert job
- [x] [P1] GitHub Actions failure notification delivery
- [x] [P1] critical P0 alert classes
- [x] [P1] Implement the convention runtime profile skeleton:
- [x] [P1] define runtime profile contract (`standard`, `convention`, `rehearsal`) and startup selector
- [x] [P1] add Fly config variants for profile-driven runtime settings
- [x] [P1] warm-mode enable/disable path
- [x] [P1] initial `Gunicorn + 3 Uvicorn workers` configuration (updated after rehearsal validation)
- [x] [P1] explicit `dev` rehearsal configuration path
- [x] [P1] add runbook commands for profile switch + verification + rollback
- [x] [P1] record convention profile switch events in deploy traceability notes

Overall execution order override:
- Keep the phase taxonomy for categorization, but execute work in this order:
  1. Phase 4B Postgres implementation
  2. Phase 4B minimum observability implementation
  3. Phase 4B convention runtime profile skeleton
  4. Phase 5 repository structure cleanup
  5. Phase 4 frontend architecture foundation implementation
  6. Phase 4 image migration implementation
  7. Phase 4 convention mode implementation  
  8. Phase 4 convention rehearsal/load testing in `dev`
  9. Later hardening phases
- Phase 4 implementation items intentionally occur before later phase categories because later phases should build on the intended architecture rather than deepen investment in transitional paths.
- [x] [P2] API versioning policy documented (`docs/policies/api_versioning_policy.md`)
- [x] [P2] Phase 4 architecture ADR recorded (`docs/adr/0001-phase-4-architecture-foundations.md`)

Postgres migration timing:
- The SQLite -> Postgres migration should occur within Phase 4, not after all phases are complete.
- Reason: later phases (testing, repository cleanup, security, CI hardening) should build on the intended production database architecture rather than deepen investment in the legacy SQLite deployment model.
- Implementation should still be sequenced conservatively:
  1. complete the architecture decision and migration plan in Phase 4
  2. implement and validate Postgres locally in WSL first
  3. cut over `dev`
  4. validate and stabilize
  5. cut over `prod`
- If the migration starts in Phase 4 and spans more than one PR, keep all related work grouped under the Phase 4 architecture track until the `prod` cutover is complete.

Phase 4 decision summary:
- Architecture decisions are recorded in:
  - `docs/adr/0001-phase-4-architecture-foundations.md`
- Cross-cutting sequencing and rollback rules are recorded in:
  - `docs/architecture/migration_cutover_strategy.md`
- Service-level targets are recorded in:
  - `docs/policies/service_level_targets.md`
- Rehearsal/load-test requirements are recorded in:
  - `docs/architecture/convention_runtime_policy.md`
- Subsystem-specific implementation details live in the relevant planning docs listed below.

Phase 4 non-functional targets:
- Defined in [Service Level Targets](../policies/service_level_targets.md).
- Phase 4 planning and implementation docs should reference that file as the canonical source rather than duplicating target values.

Related Phase 4 planning docs:
- `docs/policies/service_level_targets.md`
- `docs/architecture/postgres_migration_plan.md`
- `docs/architecture/convention_mode_access_plan.md`
- `docs/architecture/image_storage_migration_plan.md`
- `docs/architecture/convention_runtime_policy.md`
- `docs/architecture/observability_alerting_plan.md`
- `docs/architecture/frontend_architecture_plan.md`
- `docs/architecture/migration_cutover_strategy.md`
- `docs/policies/data_contract_ownership.md`
- `docs/policies/api_versioning_policy.md`
- `docs/adr/0001-phase-4-architecture-foundations.md`

### Phase 5: Repository Structure and Naming Cleanup (2-5 days)
- [x] [P1] Define target top-level layout and ownership for `backend/`, `frontend/`, pipeline code, scripts, data, and docs.
- [x] [P2] Decide whether `crawler/` should be renamed to a clearer name (for example `pipeline/` or `data_pipeline/`).
- [x] [P1] Decide final location boundaries:
- [x] [P1] runtime/import scripts that currently live in `backend/app/`
- [x] [P1] pipeline scripts vs exploratory notebooks
- [x] [P1] test utilities vs production scripts
- [x] [P1] generated artifacts vs source-controlled files
- [x] [P1] Add a file-placement policy:
- [x] [P1] no generated build outputs committed unless explicitly required
- [x] [P1] no runtime logs/DB/model artifacts in source directories
- [x] [P1] no backup files (for example `*.bak`) in production code paths
- [x] [P1] Audit and remove/relocate obsolete or duplicate files (for example duplicate test/performance scripts).
- [x] [P1] Add/update `.gitignore` rules to match artifact policy.
- [x] [P0] Remove tracked backup/temp artifacts from source control and prevent reintroduction (for example `*.bak` checks).
- [x] [P1] Define notebook policy:
- [x] [P1] where notebooks live
- [x] [P1] whether notebook data/secrets are allowed in repo
- [x] [P1] Review all existing notebooks and document:
- [x] [P1] what feature/workflow value each notebook adds
- [x] [P1] whether each notebook should remain a notebook or be converted into a script/module
- [x] [P1] ownership and maintenance expectations for notebooks kept in repo
- [x] [P1] conversion plan for notebook logic that should move to scripts
- [x] [P0] Run credential-artifact hygiene pass (notebooks/scripts) and remove blocked files (tokens/keys/secrets).
- [x] [P0] Add pre-commit/CI check to block committing known secret artifact patterns.
- [x] [P1] Add or update README coverage:
- [x] [P1] `backend/README.md` (API, migrations, local run/test)
- [x] [P1] `frontend/README.md` (dev server, build, test, env vars)
- [x] [P1] pipeline directory README (data flow, commands, outputs)
- [x] [P1] `scripts/README.md` (what each script does and when to run it)
- [x] [P1] `docs/README.md` index linking key guides and runbooks
- [x] [P1] Update root `README.md` project structure section to reflect final layout.
- [x] [P1] Record major structure decisions in ADRs.

### Phase 6: Testing Foundation (4-7 days)
- [x] [P0] Add backend API tests for `/api/games` filtering/pagination/sort.
- [x] [P0] Add backend API tests for `/api/recommendations` and `/api/recommendations/{id}`.
- [x] [P0] Add backend API tests for auth endpoints (`/api/token`, `/api/users/me`, password change).
- [x] [P1] Add backend API tests for suggestions endpoint.
- [x] [P0] Add backend edge-case tests (invalid params, unauthenticated access, empty results).
- [x] [P1] Add OpenAPI contract test.
- [x] [P1] Add frontend integration tests (auth flow, filtering, recommendation flow, API error states).
- [x] [P1] Add MSW-based API mocks for deterministic frontend tests.
- [x] [P1] Add data pipeline unit tests for `data_processor.py` and `create_embeddings.py`.
- [x] [P1] Add fixture/golden tests for output shape and key fields.
- [ ] [P0] Ensure all tests run in CI on PR.
- [x] [P1] Document test commands for backend, frontend, and pipeline in repo docs.
- [x] [P1] Document expected test runtime and minimum local prerequisites.
- [x] [P1] Add load/performance baseline tests and store reference results.
- [x] [P1] Define performance regression thresholds and failure policy.

### Phase 7: Security Hardening (2-4 days)
- [x] [P0] Remove insecure production fallback behavior for `SECRET_KEY`.
- [x] [P0] Make production startup fail if required security env vars are missing.
- [x] [P1] Add `gitleaks` to CI.
- [ ] [P1] Add Python dependency audit (`pip-audit` or equivalent) to CI.
- [ ] [P1] Add npm dependency audit policy to CI.
- [ ] [P1] Add auth behavior tests for token expiry and unauthorized response consistency.
- [ ] [P1] Review and scrub logs for sensitive data exposure.
- [x] [P1] Define outbound alert escalation channel for production incidents.
- [x] [P1] Define alert recipients and escalation path.
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
- [x] [P0] Standardize Python formatting/linting (`ruff format`, `ruff check`).
- [x] [P0] Standardize frontend formatting/linting (`eslint`, `prettier`).
- [ ] [P2] Add Python type checks for critical backend modules.
- [ ] [P0] Add required status checks in branch protection for `main`.
- [ ] [P0] Enforce merge blocking on failed lint/tests/security checks.
- [x] [P1] Add dependency update cadence (scheduled PRs + patch SLA).
- [x] [P0] Re-enable `python-quality` CI job and require it to pass.
- [x] [P0] Re-enable `frontend-build` CI job and require it to pass.
- [x] [P1] Re-enable `frontend-audit` CI job with agreed vulnerability policy (baseline/allowlist/threshold).
- [x] [P0] Make Python CI tests deterministic (CI DB fixture/setup step or deterministic subset; no silent test skips allowed).
- [x] [P1] Add a `Quality Commands` section in docs with exact local commands:
- [x] [P1] Python format/lint/fix commands (`ruff format`, `ruff check`).
- [x] [P1] Frontend format/lint commands (`prettier`, `eslint`).
- [ ] [P1] Type-check commands (frontend type checks if enabled).
- [x] [P1] Add CI mapping in docs (which command runs in which CI job).
- [x] [P1] Add troubleshooting notes for common quality-check failures.

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
- [ ] [P1] Upgrade React/testing-library stack and resolve frontend test-tooling deprecation warnings (including `act` warning paths).

### Phase 10: Observability and Operational Readiness (2-4 days)
- [ ] [P1] Add structured logs with request IDs.
- [ ] [P1] Add request timing middleware (endpoint + method + status + duration).
- [ ] [P0] Add `/health/live` endpoint.
- [ ] [P0] Add `/health/ready` endpoint with DB/model readiness checks.
- [ ] [P1] Define and document 5xx rate target.
- [ ] [P1] Define and document p95 latency target.
- [ ] [P1] Define and document auth failure alert threshold.
- [ ] [P1] Document incident triage steps in runbook.
- [x] [P0] Add production alert for missing/corrupt embeddings.
- [x] [P0] Ensure alert notifications include environment, release SHA, and failure reason.
- [ ] [P1] Add periodic embedding health check and alert on transition to degraded mode.
- [ ] [P1] Validate alert noise controls (dedupe/rate limit) to avoid spam.
- [ ] [P1] Add incident postmortem template and follow-up tracking process.
- [ ] [P1] Add release-note template that flags breaking changes and deprecations.
- [x] [P1] Document Fly operational diagnostics runbook (`fly status`, `fly releases`, machine status, and log inspection).
- [ ] [P2] Define Fly cost guardrails (budget threshold and monthly review process).
- [ ] [P2] Define alert path for unexpected Fly cost/resource growth.

### Phase 11: Architecture Cleanup and Performance (ongoing)
- [ ] [P1] Move heavy business logic from FastAPI handlers into service modules.
- [ ] [P1] Centralize frontend API calls in a dedicated service layer.
- [ ] [P1] Profile and optimize hot queries and N+1 patterns.
- [ ] [P1] Revisit cache strategy and invalidation rules.
- [ ] [P3] Optional optimization: replace O(N) total-count cache eviction scan with `OrderedDict` LRU-style eviction (avoid full-cache clear).
- [ ] [P2] Add lightweight ADRs for major architecture decisions.
- [ ] [P1] Define idempotency and retry strategy for write endpoints and ingestion jobs.
- [ ] [P1] Define timeout/retry policy for external calls and long-running jobs.
- [ ] [P0] Run memory/performance validation for `data_pipeline/src` scripts on Fly runtime targets and capture OOM-safe limits per job.
- [ ] [P0] Decide pipeline execution topology on Fly:
- [ ] [P0] whether jobs can safely run on existing app/db machines
- [ ] [P0] or require dedicated pipeline worker machines/apps with isolated sizing
- [ ] [P0] Define independent monthly cadence for pipeline rebuild jobs (outside app request path) and document trigger/ownership.
- [ ] [P0] Define canonical storage plan for pipeline outputs/artifacts:
- [ ] [P0] where raw/intermediate/final outputs live
- [ ] [P0] retention/cleanup policy
- [ ] [P0] handoff path from pipeline outputs to runtime-consumed artifacts

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
- [x] [P1] Deploy/rollback runbook exists and has been exercised.
- [ ] [P1] Known schema/contract mismatches are resolved.
- [x] [P1] Dev and prod environments are separated and documented.
- [ ] [P1] Promotion to prod requires passing pre-prod validation checklist.
- [ ] [P1] Production supports degraded recommendation mode with actionable alerts for embedding failures.
- [ ] [P1] Toolchain is modernized to Poetry `2.3.x` and latest compatible Python target (`3.13` preferred, `3.12` fallback).
- [ ] [P1] Architecture/tooling ADRs are completed and any selected architecture migrations are planned with rollback.
- [x] [P1] Repository structure, naming, and README coverage are standardized and documented.
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
