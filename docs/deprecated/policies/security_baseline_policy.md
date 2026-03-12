# Security Baseline Policy (Low-Maintenance)

## Purpose
- Define the minimum ongoing security controls for a solo-maintained project.
- Prefer controls with low recurring operational overhead.

## 1. Encryption Controls
- In transit:
  - Production traffic must use HTTPS/TLS only.
  - Auth/token endpoints must never be exposed over plain HTTP in production.
- At rest:
  - Rely on provider-managed disk/storage encryption for Fly volumes and configured object storage.
  - Keep secrets out of source control and rotate per `docs/policies/secret_management.md`.

## 2. Threat-Model Checklist (For New Public Endpoints)
Complete this checklist in PR notes for new public endpoints/features:
- What data can be read/written?
- Who is allowed to call it?
- Is auth required, and is failure behavior explicit?
- Is input validation/rate limiting required?
- Could it expose internal services (SSRF/egress risk)?
- Does it log sensitive values?
- Are test cases added for abuse/failure paths?
- Is rollback behavior clear if shipped and then disabled?

## 3. Data Retention and Minimization
- Principle:
  - Keep only what is required for app operation, troubleshooting, and recovery.
- Baseline retention:
  - App operational logs: 30 days in dev, 90 days in prod.
  - CI logs/artifacts: follow GitHub defaults unless incident response needs temporary extension.
  - Pipeline intermediate outputs: keep latest successful set; remove stale intermediates older than 30 days.
  - Backup retention: follow DB backup policy/runbook.
- Minimization:
  - Do not log secrets, bearer tokens, raw Authorization headers, or raw credential values.
  - Avoid storing unneeded personal data fields.

## 4. Bot Protection Policy
- Default:
  - Rely on existing auth + rate limits.
- Trigger to add CAPTCHA/Turnstile:
  - repeated abuse on unauthenticated or form endpoints,
  - sustained automated traffic causing availability issues.
- Until trigger is hit, keep this deferred to avoid unnecessary maintenance.

## 5. CSRF Policy (Context-Dependent)
- If cookie/session auth is introduced for sensitive write operations:
  - require CSRF protection and tests before release.
- Current token-based API auth does not require additional CSRF controls for bearer-token flows.

## 6. Network/Egress Policy (Pragmatic Baseline)
- Keep outbound access minimal to required dependencies only.
- If infrastructure-level egress controls become easy to enforce safely, add:
  - explicit allowlist for required destinations,
  - environment-specific exceptions documented in runbooks.
