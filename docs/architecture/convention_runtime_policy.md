# Convention Runtime Policy

## Purpose
- Define how production runtime behavior should change during active convention hours.
- Reduce cold-start risk and improve reliability during the event window.

## Goals
- Keep the app responsive during convention usage.
- Avoid cold-start delays during active convention hours.
- Balance reliability improvements against cost sensitivity.

## Service-Level Reference
- Canonical performance, reliability, and recovery targets are defined in [service_level_targets.md](/home/msnow/git/pax_tt_recommender/docs/policies/service_level_targets.md).
- This runtime policy exists to keep production inside those targets during convention hours.

## Convention Hours
- Convention warm window is event-specific and config-driven.
- During the configured event window, production should remain warm.

## Runtime Policy
- During convention hours, target one always-running production machine.
- Do not rely on cold-start behavior during active event usage.
- Outside convention hours, lower-cost runtime settings can still be considered if appropriate.
- Maintain a distinct convention runtime configuration so it is easy to switch between convention and non-convention settings.
- Target `Gunicorn` with `2` Uvicorn workers as the initial convention production runtime profile.

## Runtime Profile Skeleton (Phase 4B Target)
### Profile Names
- `standard`: default non-convention profile.
- `convention`: active convention-hours profile.
- `rehearsal`: dev-only temporary profile that mirrors convention runtime settings during testing windows.

### Profile Contract
- `standard` profile:
  - process model: current baseline (`uvicorn`)
  - warm setting: no always-on requirement (`min_machines_running=0`)
  - intended environments: `dev` and `prod` outside convention hours
- `convention` profile:
  - process model: `Gunicorn` + `2` Uvicorn workers
  - warm setting: one always-running machine (`min_machines_running=1`)
  - intended environment: `prod` during convention hours
- `rehearsal` profile:
  - process model: same as `convention`
  - warm setting: one always-running machine for test windows only
  - intended environment: `dev` only, explicitly enabled and later disabled

### Required Configuration Surface
- Runtime selector:
  - `RUNTIME_PROFILE` with values: `standard`, `convention`, `rehearsal`
- Process-model knobs:
  - `APP_SERVER` (`uvicorn` or `gunicorn`)
  - `GUNICORN_WORKERS` (initial target: `2` for convention/rehearsal)
- Convention schedule knobs:
  - `CONVENTION_TIMEZONE` (IANA timezone, for example `America/New_York`, `Europe/Berlin`)
  - `CONVENTION_WARM_START` (local time in `HH:MM`, for example `09:00`)
  - `CONVENTION_WARM_END` (local time in `HH:MM`, for example `00:00`)
- Optional safety knob:
  - `CONVENTION_PROFILE_LOCK=true` to prevent accidental profile drift during active hours

### Fly Config Separation
- Keep separate Fly config variants to avoid ad hoc manual edits during event operations:
  - `fly.toml` for standard production
  - `fly.convention.toml` for convention production
  - `fly.dev.toml` for standard dev
  - `fly.dev.rehearsal.toml` for dev rehearsal windows
- Each profile config should be source controlled and reviewed like code.

## Short-Term Operational Model
- Use one always-running machine as the baseline convention setting.
- Revisit multi-machine scaling only if load testing or real usage indicates it is necessary.
- Keep the first convention runtime policy simple and explicit.
- `dev` should not mirror this warm-runtime policy by default.
- Only use warm-like settings in `dev` for explicit rehearsal or load-testing windows.
- Keep the initial worker count conservative because recommendation artifacts are loaded per worker and increase memory usage linearly with worker count.
- `dev` is the designated environment for convention rehearsal and load testing.
- After rehearsal windows, `dev` should be returned to the lower-cost default profile.

## Backend Runtime Assumptions
- The current single-process raw `uvicorn` runtime is acceptable for local development and low-risk staging.
- Convention production should move to a managed process model:
  - `Gunicorn` managing `2` Uvicorn workers as the initial target
- Recommender artifacts remain on local mounted storage during the first Phase 4 implementation step.
- Each worker is expected to load its own in-memory copy of the recommendation artifacts.
- Increasing worker count above `2` requires measured validation of:
  - per-worker memory usage
  - startup/restart time
  - request latency under load

## Activation Model
- Convention runtime behavior should be enabled through an explicit operational change before the event.
- Preferred short-term approach:
  - a convention runtime config/profile
  - applied by a manual or scripted operational command
  - not by an implicit or hidden change
- The convention runtime profile should support scheduled daily enablement during the convention.
- Activation should include both:
  - runtime profile switch (`standard` -> `convention`)
  - warm setting switch (`min_machines_running=0` -> `1`)

## Deactivation Model
- After convention hours or after the event, the runtime policy may be reverted to lower-cost settings if desired.
- This should also be an explicit operational step.
- The convention runtime profile should also support scheduled daily disablement after convention hours.
- Deactivation should include both:
  - runtime profile switch (`convention` -> `standard`)
  - warm setting switch (`min_machines_running=1` -> `0`)

## Scheduling Policy
- Target daily convention runtime schedule:
  - enable warm mode at `CONVENTION_WARM_START`
  - disable warm mode at `CONVENTION_WARM_END`
- Even if the first version is applied manually, the policy should be documented as a schedule-driven runtime change.
- Schedule interpretation must use `CONVENTION_TIMEZONE` (event-local timezone), not server-local timezone.

## Related Operational Concerns
- Health checks must remain enabled and passing.
- Alerting should be in place for:
  - app health failures
  - DB connectivity failures
  - degraded recommendation mode

## Alert Thresholds
- Alert if p95 latency for `/api` or core catalog/game-list requests exceeds `1500 ms` for `5` consecutive minutes during convention hours.
- Alert if recommendation endpoint p95 latency exceeds `4000 ms` for `5` consecutive minutes during convention hours.
- Alert immediately on repeated `5xx` spikes or health-check failures.
- Escalate from one warm machine to considering additional capacity if:
  - p95 latency stays above threshold for `10+` minutes during active hours, or
  - health checks flap / restart events occur.

## Rehearsal and Load Testing
- Before convention launch, run at least one rehearsal that simulates convention-like concurrent usage.
- This rehearsal should run in the `dev` environment using temporarily applied convention-like runtime settings.
- This rehearsal should be used to validate:
  - p95 latency under representative request mix
  - memory usage with the selected worker count
  - startup/restart behavior with warm-runtime settings enabled
- Use the rehearsal results to decide whether to:
  - keep `2` workers
  - increase worker count
  - increase machine memory for the convention runtime profile
- Do not finalize convention worker count or machine sizing without this rehearsal.

## Implementation Sequence
1. Implement runtime profile selector in startup path (`RUNTIME_PROFILE` -> process command + worker count).
2. Add Fly config variants for `standard`, `convention`, and `rehearsal`.
3. Add explicit enable/disable runbook commands for:
  - `prod` convention profile
  - `dev` rehearsal profile
4. Validate profile switching without data/config regressions.
5. Validate warm-runtime settings in `dev` during explicit rehearsal/load-test windows.
6. Run a convention-condition rehearsal to measure latency and memory before locking final worker count and machine sizing.
7. Apply `convention` profile to `prod` on the convention schedule.
8. Revert `prod` to `standard` profile outside active hours when appropriate.
9. Record each profile switch event in deploy traceability notes.

## Minimum Acceptance Criteria For Phase 4B Runtime Skeleton
- Runtime profile selector exists and is documented.
- `prod` convention enable and disable command paths are documented and repeatable.
- `dev` rehearsal enable and disable command paths are documented and repeatable.
- Initial `Gunicorn + 2 Uvicorn workers` profile can be activated without failed health checks.
- One-machine warm mode can be enabled and disabled intentionally on schedule.

## Validation Criteria
- The app does not cold-start during active convention usage.
- The main app remains available through the convention window.
- The runtime policy can be enabled and disabled intentionally without ambiguity.
- The selected worker count and machine sizing are backed by measured rehearsal data rather than guesswork.
