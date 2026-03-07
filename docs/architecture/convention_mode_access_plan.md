# Convention Mode Access Plan

## Purpose
- Define how the app should behave during convention operation when read-only access is needed on controlled public devices.
- Separate guest read-only access from authenticated write access.
- Preserve lightweight personalization for shared devices without requiring account creation.

## Goals
- Allow read-only convention users to access the app with zero manual login steps on approved kiosk devices.
- Keep write actions authenticated and limited to approved users.
- Support session-scoped guest personalization on shared/public devices.
- Keep convention mode simple to enable and disable operationally.

## Non-Goals
- Do not introduce anonymous account creation in the short term.
- Do not make convention mode the default outside event windows.
- Do not use login as the primary abuse-protection mechanism for guest read traffic.

## Activation Model
- Convention mode is controlled by explicit environment flags.
- Initial implementation target:
  - `CONVENTION_MODE=true` enables convention behavior
  - `CONVENTION_GUEST_ENABLED=true` enables kiosk guest auto-login flow
  - either unset/false disables those behaviors
- This is applied as an explicit deployment/configuration change before and after convention operation.

## Access Model
### Kiosk Guest Read-Only Users
- Allowed during convention mode only.
- Intended for controlled public devices in the short term.
- No username/password entry in the UI.
- Session is established automatically using a convention guest token endpoint.
- Allowed capabilities include:
  - browse/search/filter the catalog
  - view game details
  - view recommendations
  - view public user-curated recommendation lists (for example librarian picks)
  - use temporary personalization within the current session
- Guest users should not be allowed to submit suggestions in V1.
- Guest users should have access only to an explicit allowlist of user-facing read endpoints required for these flows.

### Authenticated Write Users
- Must continue to log in even during convention mode.
- Intended for library-team members using their own devices.
- Write access includes:
  - existing authenticated write features
  - future user-curated recommendation list management
- User-curated recommendation lists (for example librarian picks) remain visible to all users, not only in convention mode.

## Guest Personalization Model
- Short-term implementation should use browser `sessionStorage`.
- Reason:
  - devices are shared/public
  - state should last for the active browser session only
  - local persistence across users is not desirable
- Candidate session-scoped state:
  - liked/disliked selections
  - current recommendation workflow state
  - other temporary read-only personalization relevant to recommendations

## Shared Device Safety Requirements
- Provide a clear `Reset Session` control to clear guest state quickly.
- Ensure guest session state is not stored durably across device users in the short term.
- Avoid `localStorage` for guest personalization unless there is a specific reason and explicit clearing logic.
- Add automatic session clearing after `3` minutes of inactivity in addition to explicit reset control.

## Security and Abuse Considerations
- Convention mode is not a substitute for network-edge protection.
- Do not rely on login to mitigate abuse from guest read traffic.
- Separate abuse-protection controls should be evaluated for the public read surface, including:
  - rate limiting
  - edge protection / WAF-style controls
  - caching of hot read endpoints

## API Contract (V1)
### Endpoint
- `POST /api/convention/guest-token`

### Purpose
- Issue a short-lived guest JWT for approved kiosk devices during convention mode.

### Required Controls
- `CONVENTION_MODE=true` must be set.
- `CONVENTION_GUEST_ENABLED=true` must be set.
- Request must include `X-Convention-Kiosk-Key: <value>`.
- Header value must match `CONVENTION_KIOSK_KEY` secret.
- Optional defense-in-depth:
  - if `CONVENTION_KIOSK_IP_ALLOWLIST` is set, caller IP must be in that allowlist.

### Success Response (`200`)
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 28800,
  "role": "guest"
}
```

### Failure Responses
- `404` when convention guest mode is disabled.
- `401` when kiosk key is missing/invalid.
- `403` when IP allowlist is configured and caller is not allowed.

### Token Contract
- Token subject: fixed guest identity (for example `guest_kiosk`).
- Token role claim: `guest`.
- Token TTL: `8` hours (refresh by calling the same endpoint again).
- Guest token permissions:
  - allow only explicit convention read allowlist endpoints
  - deny all write/admin endpoints

## API Design Implications
- Read endpoints should be reviewed and classified as:
  - safe for guest access during convention mode
  - still requiring authenticated user/admin roles
- Do not treat all read endpoints as automatically public; use an explicit allowlist.
- Write endpoints must continue to enforce authentication regardless of convention mode.
- Suggestion submission remains authenticated in V1.
- Convention checks should be explicit and testable.

## Initial Guest Read Allowlist
- `GET /api`
- `GET /api/version` (optional but safe)
- `GET /api/games/`
- `GET /api/games/{game_id}`
- `GET /api/recommendations/{game_id}`
- `POST /api/recommendations` (read-only recommendation computation for session personalization)
- `GET /api/recommendations/status`
- `GET /api/filter-options/`
- `GET /api/mechanics/`
- `GET /api/mechanics/by_frequency`
- `GET /api/categories/`
- `GET /api/categories/by_frequency`
- `GET /api/pax_game_ids`
- future public read endpoints for librarian picks

## Frontend Contract (V1)
- Add kiosk boot behavior controlled by `REACT_APP_CONVENTION_KIOSK=true`.
- On app start:
  1. call `POST /api/convention/guest-token` with `X-Convention-Kiosk-Key`
  2. store returned token in session auth state
  3. continue to normal app shell with guest permissions
- If guest-token call fails:
  - show blocking "kiosk unavailable" state
  - do not silently fall back to unauthenticated public mode
- Existing staff login flow remains unchanged and available.

## Convention Mode Enforcement
- Prefer explicit route-level dependency / endpoint classification over broad middleware in the first implementation.
- Reason:
  - easier to audit
  - easier to test
  - lower risk of accidentally exposing unintended endpoints

## Implementation Checklist (No-Code Planning Baseline)
1. Add flags/secrets:
  - `CONVENTION_MODE`
  - `CONVENTION_GUEST_ENABLED`
  - `CONVENTION_KIOSK_KEY`
  - optional `CONVENTION_KIOSK_IP_ALLOWLIST`
2. Implement `POST /api/convention/guest-token` contract and gating.
3. Add guest role dependency checks on protected endpoints.
4. Implement explicit guest read allowlist for convention-mode flows.
5. Keep write/admin endpoints authenticated and deny guest role.
6. Add frontend kiosk boot behavior for automatic guest token acquisition.
7. Add `sessionStorage` support for guest personalization state.
8. Add explicit `Reset Session` control.
9. Add `3` minute inactivity auto-clear.
10. Validate mode on/off and access controls.

## Validation Criteria
- Kiosk devices can acquire a guest token only when convention mode is enabled.
- Guest users can use approved read flows without manual login.
- Guest users cannot access write actions.
- Authenticated write users continue to work normally.
- Session-scoped personalization resets correctly on shared devices.
- When convention mode is disabled, current auth protections still apply.
