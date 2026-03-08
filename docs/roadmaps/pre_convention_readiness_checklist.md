# Pre-Convention Readiness Checklist

## Purpose
- Track the work that must be completed before the app is ready for convention use.
- Separate launch-critical convention work from the broader best-practices migration roadmap.

## Usage
- Use this as the canonical launch gate for convention readiness.
- Keep ad hoc follow-ups in [backlog.md](/home/msnow/git/pax_tt_recommender/docs/roadmaps/backlog.md).
- Keep `docs/roadmaps/best_practices_migration_guide.md` for long-horizon engineering and architecture work.

## Priority Legend
- `P0`: must complete before the convention
- `P1`: should complete before the convention if feasible
- `P2`: useful, but can defer if the core launch path is stable

## Access and Auth
- [ ] [P0] Implement convention mode with explicit `CONVENTION_MODE` toggle.
- [ ] [P0] Implement kiosk guest auto-login flow for approved devices via `POST /api/convention/guest-token`.
- [ ] [P0] Add required convention guest config:
  - `CONVENTION_GUEST_ENABLED`
  - `CONVENTION_KIOSK_KEY`
  - optional `CONVENTION_KIOSK_IP_ALLOWLIST`
- [ ] [P0] Implement guest read-only access allowlist for convention endpoints.
- [ ] [P0] Keep write endpoints authenticated during convention mode.
- [ ] [P0] Implement shared-device guest session state using `sessionStorage`.
- [ ] [P0] Add explicit `Reset Session` control for shared devices.
- [ ] [P0] Implement 3-minute inactivity auto-clear for guest session state.
- [ ] [P1] Validate convention-mode endpoint allowlist against the final frontend flows.

## Data and Storage
- [x] [P0] Add `DATABASE_URL` support with SQLite fallback.
- [x] [P0] Stand up native local Postgres in WSL and validate local app behavior.
- [x] [P0] Build and validate the SQLite -> Postgres migration path locally.
- [x] [P0] Provision and cut over `dev` to self-managed Postgres on Fly.
- [x] [P0] Validate `dev` on Postgres.
- [x] [P0] Provision and cut over `prod` to self-managed Postgres on Fly.
- [x] [P0] Validate `prod` on Postgres and retain SQLite rollback path during stabilization.
- [x] [P0] Define and test backup procedure for self-managed Postgres on Fly.
- [x] [P0] Define and test restore procedure for self-managed Postgres on Fly.
- [x] [P0] Make the production app fail fast when `DATABASE_URL` is missing before the final Postgres production cutover.
- [ ] [P0] Create Cloudflare R2 bucket and define canonical image URL/key config.
- [ ] [P0] Build the seeded image backfill pipeline for:
  - convention/library-relevant games
  - top `10,000` ranked games
- [ ] [P0] Build the ongoing image-sync script for qualifying games.
- [ ] [P0] Wire import/update flows to trigger image-sync checks.
- [ ] [P0] Cut `dev` over to R2-backed image delivery and validate.
- [ ] [P0] Cut `prod` over to R2-backed image delivery and validate.
- [ ] [P1] Confirm placeholder behavior is clean for missing images.
- [ ] [P1] Fix the missing placeholder asset path so image fallbacks do not request `/placeholder.png` and return `404`.
- [ ] [P1] Fix mojibake in game description text for non-English content (for example BGG `407176`) so UTF-8 descriptions render correctly in the game dialog.

## Runtime and Scaling
- [x] [P0] Implement convention runtime profile/config.
- [ ] [P0] Add per-event convention schedule config:
  - `CONVENTION_TIMEZONE`
  - `CONVENTION_WARM_START`
  - `CONVENTION_WARM_END`
- [ ] [P0] Add scheduled convention-hours warm-mode enable/disable procedure.
- [x] [P0] Add initial production convention runtime target:
  - one always-running machine
  - `Gunicorn` + `3` Uvicorn workers
- [x] [P1] Ensure `dev` can temporarily mirror convention runtime settings for rehearsal.
- [ ] [P0] Confirm health checks remain enabled and passing under convention runtime settings.

## Observability and Alerting
- [x] [P0] Implement periodic production health-check/alert job.
- [x] [P0] Use GitHub Actions failure notifications as the production alert channel.
- [x] [P0] Alert on app unreachable / health failure.
- [x] [P0] Alert on recommendation degraded mode.
- [x] [P0] Alert on database connectivity failure.
- [ ] [P1] Alert on sustained latency breach.
- [ ] [P1] Alert on auth anomaly threshold.
- [ ] [P1] Add alert dedupe/cooldown controls.
- [ ] [P1] Add recovery notifications for major alert classes.
- [ ] [P0] Test the full production alert path before convention launch.
  - Static smoke check:
    - `poetry run python scripts/validate/validate_prod_alert_path.py --env prod --skip-runtime`
  - Runtime dry-run check:
    - `poetry run python scripts/validate/validate_prod_alert_path.py --env prod`

## Rehearsal and Validation
- [x] [P0] Run a convention-condition rehearsal in `dev`.
- [ ] [P0] Measure and record:
  - p95 latency for catalog endpoints
  - p95 latency for recommendation endpoints
  - per-worker memory usage
  - startup/restart time
- [x] [P0] Use rehearsal results to confirm or adjust:
  - worker count
  - machine memory
  - convention runtime profile
- [x] [P0] Verify service-level targets are met under rehearsal conditions.
- [ ] [P0] Run rollback drill for the current production deployment model.
- [ ] [P1] Run a full pre-convention validation pass using the deploy/rollback runbook.

## Data Refresh and Operations
- [ ] [P0] Finalize and document the offline rebuild -> cutover data refresh procedure.
- [ ] [P0] Confirm no live rebuilds will run during convention hours.
- [ ] [P0] Validate the monthly rebuild path against the new Postgres + R2 architecture.
- [ ] [P0] Validate manual refresh trigger procedure.
- [ ] [P0] Validate `data_pipeline/src` jobs on Fly runtime targets and record OOM-safe CPU/RAM/job sizing.
- [ ] [P0] Decide and document pipeline execution topology before convention:
  - run on existing app/db machines
  - or run on dedicated pipeline worker machines/apps
- [ ] [P0] Define and validate canonical storage path for monthly rebuild outputs/artifacts, including retention and runtime handoff.

## Convention-Day Operations
- [ ] [P0] Create a pre-opening checklist for each convention day.
- [ ] [P0] Create an active-hours monitoring checklist.
- [ ] [P0] Create a post-closing revert-to-normal checklist.
- [x] [P0] Add manual workflow toggle step for production health alerts:
  - Pre-opening: enable scheduled checks
    - `gh workflow enable prod-health-alerts.yml`
    - GitHub UI:
      1. Open repository `Actions`
      2. Select workflow `Prod Health Alerts`
      3. Click `...` (top-right)
      4. Click `Enable workflow`
  - Post-closing: disable scheduled checks
    - `gh workflow disable prod-health-alerts.yml`
    - GitHub UI:
      1. Open repository `Actions`
      2. Select workflow `Prod Health Alerts`
      3. Click `...` (top-right)
      4. Click `Disable workflow`
- [ ] [P1] Document exact owner actions for:
  - app down
  - degraded recommendations
  - DB connectivity issue
  - image delivery issue

## Deferred / Out of Scope Unless Needed For Launch
- [ ] [P2] Decide whether the librarian-picks feature is required for the convention launch.
- [ ] [P2] If librarian picks are in launch scope, move them into a dedicated launch feature checklist with their own implementation and validation items.
