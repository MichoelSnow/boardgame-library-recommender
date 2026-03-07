# Observability and Alerting Plan

## Purpose
- Define the initial observability and alerting model for `pax_tt_recommender`.
- Keep the convention-launch operational footprint simple, low-cost, and actionable for a single developer.

## Scope
- Applies to production operations and convention-hour monitoring.
- Covers:
  - log source
  - alert transport
  - alert classes
  - noise-control expectations
- Does not introduce a full centralized logging platform in the first implementation.

## Service-Level Reference
- Canonical performance, reliability, and recovery targets are defined in [service_level_targets.md](/home/msnow/git/pax_tt_recommender/docs/policies/service_level_targets.md).
- Alerts should be aligned to those targets.

## V1 Decisions
- Do not introduce dedicated centralized log aggregation in the initial convention build.
- Use Fly logs as the operational log source for investigation and debugging.
- Add production email alerting before convention launch.
- Use a periodic health-check/alert job to detect critical failures proactively.
- Preferred V1 implementation:
  - GitHub Actions scheduled workflow as the periodic check runner
  - Resend as the preferred email delivery provider
  - SendGrid as the fallback email provider if needed

## Logging Source
- Primary operational log source:
  - Fly application logs (`fly logs`)
- Existing local file logs under `logs/` remain useful for local tooling and traceability but are not the primary production observability source.

## Alert Channel
- Required production alert channel:
  - email
- Primary recipient:
  - you
- Additional recipients may be added later, but are not required for the first implementation.

## Preferred Provider Setup
- Periodic check runner:
  - GitHub Actions scheduled workflow
- Preferred email provider:
  - Resend
- Fallback email provider:
  - SendGrid
- Raw SMTP is not the preferred first implementation.

Implementation status:
- Implemented:
  - `.github/workflows/prod-health-alerts.yml` (runs every 20 minutes + manual trigger)
  - `scripts/run_prod_health_alerts.py` (P0 health checks + email delivery)
- Runtime gating:
  - checks are skipped unless `CONVENTION_MODE=true` (read from `/api/version`)
- Provider behavior:
  - Resend is attempted first when `RESEND_API_KEY` is set
  - SendGrid is used as fallback when Resend fails or is not configured and `SENDGRID_API_KEY` is set

## Required Alert Classes
### P0 Alerts
- App unreachable / health failure
  - repeated failed health checks
  - repeated non-200 responses from the external health check
- Recommendation degraded mode
  - embeddings missing
  - corrupt or failed artifact load
  - recommendation state transitions from healthy to degraded
- Database connectivity failure
  - the app cannot reach the primary database

### P1 Alerts
- Sustained latency breach
  - request latency remains above service-level targets for a sustained window
- Auth anomaly threshold
  - repeated login failures above a defined threshold
- Unexpected resource growth
  - CPU, memory, or other Fly resource behavior indicates likely instability or runaway cost

## Detection Strategy
- Use a periodic production health-check/alert job as the primary V1 detection mechanism.
- This job should check, at minimum:
  - `/api`
  - response time
  - recommendation availability state
  - optionally a canonical recommendation smoke-check path
- The job should trigger email alerts when thresholds or unhealthy states are met.
- GitHub Actions is the preferred first scheduler because:
  - it is already part of the repo's operational workflow
  - it avoids introducing another always-on service
  - it keeps the health-check logic version-controlled with the app

## Noise Control
- Alerting must include:
  - dedupe for repeated identical failures
  - cooldowns to prevent repeated spam
  - recovery notifications for major alert classes
- Recommendation degraded-mode alerts should trigger on state transition, not on every repeated check.

## Operational Workflow
1. Health-check/alert job detects an unhealthy condition.
2. Email alert is sent with:
- environment
- failure type
- current release SHA when available
- brief reason/context
3. Investigate using:
```bash
fly logs -a pax-tt-app
```
4. Follow the deploy/rollback runbook if remediation is required.

## Deferred for Later
- Dedicated centralized log aggregation
- More advanced incident tooling (paging systems, on-call rotation)
- Multi-recipient escalation trees
- Replacing the GitHub Actions check runner with a dedicated monitoring service unless later scale or reliability needs justify it

## Exit Criteria
- Production has a periodic health-check/alert path.
- Email alerts are delivered for all required P0 alert classes.
- Alerting behavior includes dedupe/cooldown controls.
- The alert path is tested before convention launch.

## Runtime Configuration
- No required secrets for baseline operation (GitHub failure notifications).
- Optional secrets for provider-based email delivery:
  - `ALERT_EMAIL_TO` (comma-separated recipient emails)
  - `ALERT_EMAIL_FROM` (verified sender address)
  - `RESEND_API_KEY` (preferred provider)
  - `SENDGRID_API_KEY` (fallback provider)
