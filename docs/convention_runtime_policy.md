# Convention Runtime Policy

## Purpose
- Define how production runtime behavior should change during active convention hours.
- Reduce cold-start risk and improve reliability during the event window.

## Goals
- Keep the app responsive during convention usage.
- Avoid cold-start delays during active convention hours.
- Balance reliability improvements against cost sensitivity.

## Convention Hours
- Target active window:
  - 9:00 AM to 12:00 AM
- During this window, production should remain warm.

## Runtime Policy
- During convention hours, target one always-running production machine.
- Do not rely on cold-start behavior during active event usage.
- Outside convention hours, lower-cost runtime settings can still be considered if appropriate.
- Maintain a distinct convention runtime configuration so it is easy to switch between convention and non-convention settings.

## Short-Term Operational Model
- Use one always-running machine as the baseline convention setting.
- Revisit multi-machine scaling only if load testing or real usage indicates it is necessary.
- Keep the first convention runtime policy simple and explicit.
- `dev` should not mirror this warm-runtime policy by default.
- Only use warm-like settings in `dev` for explicit rehearsal or load-testing windows.

## Activation Model
- Convention runtime behavior should be enabled through an explicit operational change before the event.
- Preferred short-term approach:
  - a convention runtime config/profile
  - applied by a manual or scripted operational command
  - not by an implicit or hidden change
- The convention runtime profile should support scheduled daily enablement during the convention.

## Deactivation Model
- After convention hours or after the event, the runtime policy may be reverted to lower-cost settings if desired.
- This should also be an explicit operational step.
- The convention runtime profile should also support scheduled daily disablement after convention hours.

## Scheduling Policy
- Target daily convention runtime schedule:
  - enable warm mode before `9:00 AM`
  - disable warm mode after `12:00 AM`
- Even if the first version is applied manually, the policy should be documented as a schedule-driven runtime change.

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

## Implementation Sequence
1. Define the exact Fly runtime changes needed to keep one machine warm.
2. Package those changes as a distinct convention runtime config/profile.
3. Add enable/disable steps to the deploy/operations runbook.
4. Validate the warm-runtime settings in `dev` only when explicit rehearsal or load testing is needed.
5. Apply the warm-runtime policy to `prod` on the convention schedule.
6. Revert deliberately after the convention or outside the active daily window when appropriate.

## Validation Criteria
- The app does not cold-start during active convention usage.
- The main app remains available through the convention window.
- The runtime policy can be enabled and disabled intentionally without ambiguity.
