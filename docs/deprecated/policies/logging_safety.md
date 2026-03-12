# Logging Safety Policy (Minimal-Overhead)

## Goal
- Keep logs useful for debugging while preventing accidental secret exposure.

## Never Log
- Passwords (`password`, `current_password`, `new_password`)
- Tokens/cookies (`access_token`, `refresh_token`, `Authorization`, `Cookie`)
- Secret values (`SECRET_KEY`, API keys, database credentials)
- Raw auth request payloads

## Allowed Logging Pattern
- Log identifiers and context, not sensitive payloads.
- Preferred fields:
  - user id / username
  - endpoint path
  - status code
  - error class/message (sanitized)

## Existing Practice in This Repo
- Auth endpoints return generic credential errors.
- HTTP exception handler preserves protocol headers without logging secret-bearing headers.
- Proxy-image failures no longer log raw user-supplied URL values.

## Low-Maintenance Periodic Check
Run occasionally (or before major releases):

```bash
rg -n "logger\\.|print\\(" backend scripts | rg -i "password|token|secret|authorization|cookie|api[_-]?key"
```

If any hit logs sensitive values directly, replace with a sanitized message.
