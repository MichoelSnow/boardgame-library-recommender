# Convention Operations

## Purpose
Operational policy for convention periods where availability and latency are prioritized over cost optimization.

## Service Targets Reference
Convention runtime choices should align with:
- [docs/core/ownership_and_slos.md](/docs/core/ownership_and_slos.md)

## Runtime Profiles
- `standard`
  - default non-convention profile.
- `convention`
  - active convention-hours profile for production.
- `rehearsal`
  - dev-only profile used to simulate convention runtime settings.

## Current Convention Baseline
- Process model: `gunicorn` + Uvicorn workers.
- Baseline workers: `3`.
- Warm setting during active convention window: keep at least one machine running.

## Runtime Configuration Surface
Primary knobs:
- `RUNTIME_PROFILE` (`standard`, `convention`, `rehearsal`)
- `APP_SERVER` (`uvicorn` or `gunicorn`)
- `GUNICORN_WORKERS`
- `GUNICORN_CMD_ARGS` (convention baseline includes higher timeout)

Convention schedule knobs:
- `CONVENTION_TIMEZONE`
- `CONVENTION_WARM_START` (`HH:MM`)
- `CONVENTION_WARM_END` (`HH:MM`)

Optional safety knob:
- `CONVENTION_PROFILE_LOCK=true`

## Fly Config Variants
Use explicit Fly config files per profile/environment to avoid ad hoc edits during event operations:
- `fly.toml`
  - standard production profile baseline.
- `fly.convention.toml`
  - convention production profile (warm runtime + convention process settings).
- `fly.dev.toml`
  - standard development profile baseline.
- `fly.convention.dev.toml`
  - dev convention profile for full convention-mode validation windows.

Policy:
- Treat these files as source-controlled runtime contracts.
- Switch profiles by selecting the correct config file, not by manual one-off edits.

## Activation and Deactivation Policy
- Activation and deactivation must be explicit, repeatable operational actions.
- Convention mode should be schedule-driven and timezone-aware (event-local timezone).
- Record profile switch events in deploy traceability notes.

## Rehearsal Policy (Required Before Event)
- Run rehearsal in `dev` using convention-like runtime settings.
- Validate:
  - p95 latency under mixed representative traffic
  - error rate
  - startup/restart behavior
  - memory headroom
- Use measured rehearsal data to confirm or change worker count and machine sizing.

## Event-Time Validation Checklist
- API health endpoints are healthy.
- Recommendation endpoint remains responsive.
- No restart flapping.
- p95 latency remains within target band.
- Error rate remains below target thresholds.

## Alerting
Alert channel and delivery:
- GitHub Actions workflow-failure notifications.
- Primary recipient: repository owner/maintainer.

Implemented components:
- `.github/workflows/prod-health-alerts.yml`
- `scripts/alerts/run_prod_health_alerts.py`

Behavior:
- Scheduled every 20 minutes.
- Supports manual workflow dispatch/manual script run.
- Runtime-gated: checks are skipped unless convention mode is active.
- Embedding degraded-mode alerting is transition-based:
  - alert on healthy/ready -> degraded transition
  - suppress repeated degraded alerts when state remains degraded.
- Noise control:
  - per-event cooldown window (default 3 hours) in `run_prod_health_alerts.py`
  - persisted state file (`.alert_state/prod_health_alert_state.json`) reused across scheduled runs via workflow cache.

Alerting controls:
- Enable schedule:
  - `gh workflow enable prod-health-alerts.yml`
- Disable schedule:
  - `gh workflow disable prod-health-alerts.yml`
- Manual run:
  - `poetry run python scripts/alerts/run_prod_health_alerts.py --env prod`
  - `poetry run python scripts/alerts/run_prod_health_alerts.py --env prod --dry-run`

## Image Operations
Primary path:
- Seed from BGG to Fly local image volume.

Backup path:
- Reseed from BGG origin into Fly-local image storage when needed.

## Related Operations
For exact commands and operational sequences, use:
- [docs/core/command_reference.md](/docs/core/command_reference.md)
- [docs/core/runbook.md](/docs/core/runbook.md)
