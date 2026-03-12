# Security

## Baseline
- Keep controls low-maintenance but explicit.
- Prioritize auth safety, rate limits, header hardening, and secret hygiene.

## Encryption Controls
- In transit:
  - production traffic must be HTTPS/TLS only.
  - auth/token endpoints must not be exposed over plain HTTP.
- At rest:
  - rely on provider-managed encryption for Fly volumes and configured object storage.

## Secret Management
- Owner: repository maintainer.
- Cadence: rotate high-impact secrets every 6 months.
- Emergency rotate immediately on suspected exposure.

### High-impact secret set
- GitHub: `FLY_API_TOKEN`, `GEMINI_API_KEY`
- Fly apps: `SECRET_KEY`, `DATABASE_URL`, `CONVENTION_KIOSK_KEY`, `R2_*`
- Local: `.env` equivalents used for auth/deploy/ingest paths

### Emergency rotation steps
1. Generate replacement secret.
2. Update secret store (dev first, then prod).
3. Redeploy.
4. Validate auth + critical paths.
5. Revoke old credential where supported.
6. Record rotation event.

## How To Rotate by Location

### 1) Rotate GitHub Actions secrets
1. Go to: `GitHub repo -> Settings -> Secrets and variables -> Actions`.
2. Update the relevant secret(s), e.g.:
   - `FLY_API_TOKEN`
   - `GEMINI_API_KEY`
3. Re-run the affected workflow to validate:
   - deploy workflow for `FLY_API_TOKEN`
   - `PR Agent` workflow for `GEMINI_API_KEY`

### 2) Rotate Fly secrets (do `dev` first, then `prod`)
1. Generate a new value.
2. Set in `dev`:
   ```bash
   fly secrets set -a pax-tt-app-dev SECRET_KEY="<new-secret>"
   ```
   Repeat for any other keys being rotated (`DATABASE_URL`, `CONVENTION_KIOSK_KEY`, `R2_*`).
3. Validate `dev`:
   - `/api/version` responds
   - auth works (`/api/token` + `/api/users/me/`)
   - image paths work if rotating `R2_*`
4. Set the same rotation in `prod`:
   ```bash
   fly secrets set -a pax-tt-app SECRET_KEY="<new-secret>"
   ```
5. Validate `prod` with the same checks.

### 3) Rotate local development secrets
1. Update `.env` values (or shell exports).
2. Restart local app process.
3. Validate local auth/login and any affected script paths.

## Logging Safety
Never log:
- passwords
- bearer tokens/cookies
- raw Authorization header
- secret values

Prefer logging identifiers, endpoint path, status code, and sanitized error messages.

### Low-Maintenance Periodic Check
Run occasionally (or before major releases):

```bash
rg -n "logger\\.|print\\(" backend scripts | rg -i "password|token|secret|authorization|cookie|api[_-]?key"
```

If any hit logs sensitive values directly, replace with a sanitized message.

## CSP Baseline
- API (`/api/*`):
  - `default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'`
  - optional override: `API_CSP`
- Frontend/static (default):
  - `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https:; font-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`
- Optional override via `FRONTEND_CSP`.

## Rate Limit Client IP Trust
- Default behavior ignores `X-Forwarded-For` for rate-limit keys.
- To trust proxy-provided client IPs, set `TRUST_X_FORWARDED_FOR=true`.
- Only enable trust mode when traffic is behind a trusted proxy that strips untrusted forwarding headers.

## Threat Model Lite Checklist (for new public endpoints)
- Data exposed/modified?
- Required auth and failure behavior?
- Input validation and rate limit needed?
- SSRF/internal-access risk?
- Sensitive logging risk?
- Abuse/failure tests added?

## Data Retention and Minimization
- App logs: 30 days dev, 90 days prod.
- Pipeline intermediates: keep latest successful set; clean stale >30 days.
- Do not store/log unneeded sensitive data.

## Context-dependent Controls
- CSRF protections required if cookie/session auth is introduced for sensitive writes.
- File upload malware scanning required if uploads are introduced.
- Bot protection (captcha/turnstile) only when abuse signal justifies it.
