# Pre-Convention Readiness Checklist

## Purpose
- Track the work that must be completed before the app is ready for convention use.
- Separate launch-critical convention work from the broader best-practices migration roadmap.

## Usage
- Use this as the canonical launch gate for convention readiness.
- Keep `todo.md` for short-lived notes and ad hoc follow-ups.
- Keep `docs/roadmaps/best_practices_migration_guide.md` for long-horizon engineering and architecture work.

## Priority Legend
- `P0`: must complete before the convention
- `P1`: should complete before the convention if feasible
- `P2`: useful, but can defer if the core launch path is stable

## Access and Auth
- [ ] [P0] Implement convention mode with explicit `CONVENTION_MODE` toggle.
- [ ] [P0] Implement anonymous read-only access for allowed convention endpoints.
- [ ] [P0] Keep write endpoints authenticated during convention mode.
- [ ] [P0] Implement shared-device anonymous session state using `sessionStorage`.
- [ ] [P0] Add explicit `Reset Session` control for shared devices.
- [ ] [P0] Implement 3-minute inactivity auto-clear for anonymous session state.
- [ ] [P1] Validate convention-mode endpoint allowlist against the final frontend flows.

## Data and Storage
- [x] [P0] Add `DATABASE_URL` support with SQLite fallback.
- [x] [P0] Stand up native local Postgres in WSL and validate local app behavior.
- [x] [P0] Build and validate the SQLite -> Postgres migration path locally.
- [x] [P0] Provision and cut over `dev` to self-managed Postgres on Fly.
- [x] [P0] Validate `dev` on Postgres.
- [ ] [P0] Provision and cut over `prod` to self-managed Postgres on Fly.
- [ ] [P0] Validate `prod` on Postgres and retain SQLite rollback path during stabilization.
- [x] [P0] Define and test backup procedure for self-managed Postgres on Fly.
- [x] [P0] Define and test restore procedure for self-managed Postgres on Fly.
- [ ] [P0] Make the production app fail fast when `DATABASE_URL` is missing before the final Postgres production cutover.
- [ ] [P0] Create Cloudflare R2 bucket and define canonical image URL/key config.
- [ ] [P0] Build the seeded image backfill pipeline for:
  - convention/library-relevant games
  - top `10,000` ranked games
- [ ] [P0] Build the ongoing image-sync script for qualifying games.
- [ ] [P0] Wire import/update flows to trigger image-sync checks.
- [ ] [P0] Cut `dev` over to R2-backed image delivery and validate.
- [ ] [P0] Cut `prod` over to R2-backed image delivery and validate.
- [ ] [P1] Confirm placeholder behavior is clean for missing images.

## Runtime and Scaling
- [ ] [P0] Implement convention runtime profile/config.
- [ ] [P0] Add scheduled convention-hours warm-mode enable/disable procedure.
- [ ] [P0] Add initial production convention runtime target:
  - one always-running machine
  - `Gunicorn` + `2` Uvicorn workers
- [ ] [P1] Ensure `dev` can temporarily mirror convention runtime settings for rehearsal.
- [ ] [P0] Confirm health checks remain enabled and passing under convention runtime settings.

## Observability and Alerting
- [ ] [P0] Implement periodic production health-check/alert job.
- [ ] [P0] Integrate Resend for production email alerts.
- [ ] [P1] Add SendGrid fallback plan/config if Resend is not viable.
- [ ] [P0] Alert on app unreachable / health failure.
- [ ] [P0] Alert on recommendation degraded mode.
- [ ] [P0] Alert on database connectivity failure.
- [ ] [P1] Alert on sustained latency breach.
- [ ] [P1] Alert on auth anomaly threshold.
- [ ] [P1] Add alert dedupe/cooldown controls.
- [ ] [P1] Add recovery notifications for major alert classes.
- [ ] [P0] Test the full production alert path before convention launch.

## Rehearsal and Validation
- [ ] [P0] Run a convention-condition rehearsal in `dev`.
- [ ] [P0] Measure and record:
  - p95 latency for catalog endpoints
  - p95 latency for recommendation endpoints
  - per-worker memory usage
  - startup/restart time
- [ ] [P0] Use rehearsal results to confirm or adjust:
  - worker count
  - machine memory
  - convention runtime profile
- [ ] [P0] Verify service-level targets are met under rehearsal conditions.
- [ ] [P0] Run rollback drill for the current production deployment model.
- [ ] [P1] Run a full pre-convention validation pass using the deploy/rollback runbook.

## Data Refresh and Operations
- [ ] [P0] Finalize and document the offline rebuild -> cutover data refresh procedure.
- [ ] [P0] Confirm no live rebuilds will run during convention hours.
- [ ] [P1] Validate the monthly rebuild path against the new Postgres + R2 architecture.
- [ ] [P1] Validate manual refresh trigger procedure.

## Convention-Day Operations
- [ ] [P0] Create a pre-opening checklist for each convention day.
- [ ] [P0] Create an active-hours monitoring checklist.
- [ ] [P0] Create a post-closing revert-to-normal checklist.
- [ ] [P1] Document exact owner actions for:
  - app down
  - degraded recommendations
  - DB connectivity issue
  - image delivery issue

## Deferred / Out of Scope Unless Needed For Launch
- [ ] [P2] Decide whether the librarian-picks feature is required for the convention launch.
- [ ] [P2] If librarian picks are in launch scope, move them into a dedicated launch feature checklist with their own implementation and validation items.
