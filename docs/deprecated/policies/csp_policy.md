# Content Security Policy (CSP) Baseline

## Objective
- Enforce a safe CSP baseline with minimal maintenance overhead.
- Keep API responses locked down, while allowing frontend static assets to function.

## Runtime Policy

### API Responses (`/api/*`)
- Header: `Content-Security-Policy`
- Value:
  ```text
  default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'
  ```
- Rationale: API JSON responses should not execute scripts, load external assets, or be framed.

### Frontend/Static Responses (non-`/api/*`)
- Default value:
  ```text
  default-src 'self';
  script-src 'self';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data: https:;
  connect-src 'self' https:;
  font-src 'self' data:;
  frame-ancestors 'none';
  base-uri 'self';
  form-action 'self'
  ```
- Optional override:
  - `FRONTEND_CSP` environment variable (full header value).

## Production Validation

```bash
curl -sI https://bg-lib-app.fly.dev/api/version | rg -i "content-security-policy|strict-transport-security|x-content-type-options|x-frame-options"
curl -sI https://bg-lib-app.fly.dev/ | rg -i "content-security-policy"
```

Expected:
- `/api/version` returns strict API CSP.
- `/` returns frontend CSP.
- In production mode, `Strict-Transport-Security` is present.

## Maintenance Notes
- Add new origins/resources only when required by actual frontend/runtime behavior.
- Prefer updating `FRONTEND_CSP` env var rather than code changes when tuning policy.
