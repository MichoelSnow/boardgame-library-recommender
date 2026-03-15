# Convention Mode Access Plan

Status: Active design document  
Exit criteria: move to `docs/deprecated/` once guest mode is implemented and validated in production

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
- Guest users may submit suggestions in V1; suggestions are stored under the fixed guest identity.
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
- Add automatic session clearing after `5` minutes of inactivity in addition to explicit reset control.

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
- Caller must already be enrolled as a kiosk browser/device (valid signed kiosk cookie marker).

### Success Response (`200`)
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

### Failure Responses
- `404` when convention guest mode is disabled.
- `401` when kiosk enrollment marker is missing/invalid.

### Token Contract
- Token subject: fixed guest identity (for example `guest_kiosk`).
- Token role claim: `guest`.
- Token TTL: `17` hours (refresh by calling the same endpoint again).
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
- `GET /api/library_game_ids`
- future public read endpoints for librarian picks

## Frontend Contract (V1)
- Use explicit device enrollment for kiosk mode; do not rely on build-time frontend env flags as the primary selector.
- On a designated kiosk device (one-time per browser profile):
  1. open kiosk setup UI (for example `/kiosk/setup`)
  2. sign in as admin and click `Enroll This Device`
  3. backend validates mode + admin auth and marks browser as kiosk (signed cookie/server-validated marker)
- On app start:
  1. call kiosk status endpoint (for example `GET /api/convention/kiosk/status`)
  2. if `kiosk_mode=true`, call `POST /api/convention/guest-token` with kiosk credentials/marker
  3. store returned token in session auth state and continue in kiosk UX mode
- If kiosk guest-token acquisition fails:
  - show blocking "kiosk unavailable" state with:
    - `Retry Guest Mode`
    - `Staff Login`
  - do not silently fall back to unauthenticated public mode
- Non-enrolled devices remain in normal mode, even when `CONVENTION_MODE=true`.
- Existing staff login flow remains unchanged and available.

## Kiosk Device Enrollment Flow (Recommended)
1. Convention operator enables convention flags:
  - `CONVENTION_MODE=true`
  - `CONVENTION_GUEST_ENABLED=true`
2. Operator enrolls each kiosk browser once:
  - open `/kiosk/setup` and enroll as admin
  - backend returns success and sets signed `kiosk_mode` marker for that browser
3. Enrolled kiosk browser automatically boots into guest flow on app load.
4. Non-enrolled devices (staff or public) do not get kiosk behavior.
5. Unenroll/revoke options:
  - use `/kiosk/setup` admin flow to remove kiosk marker on that browser
  - optional server-side invalidation for active kiosk markers

## Convention Mode Enforcement
- Prefer explicit route-level dependency / endpoint classification over broad middleware in the first implementation.
- Reason:
  - easier to audit
  - easier to test
  - lower risk of accidentally exposing unintended endpoints

## Implementation Checklist
1. Add flags/secrets:
  - `CONVENTION_MODE`
  - `CONVENTION_GUEST_ENABLED`
2. Implement `POST /api/convention/guest-token` contract and gating.
3. Add guest role dependency checks on protected endpoints.
4. Implement explicit guest read allowlist for convention-mode flows.
5. Keep write/admin endpoints authenticated and deny guest role, except explicitly allowed guest suggestion submission.
6. Add frontend kiosk boot behavior for automatic guest token acquisition.
7. Add `sessionStorage` support for guest personalization state.
8. Add explicit `Reset Session` control.
9. Add `5` minute inactivity auto-clear.
10. [x] Validate mode on/off and access controls.

## Validation Criteria
- Kiosk devices can acquire a guest token only when convention mode is enabled.
- Guest users can use approved read flows without manual login.
- Guest users cannot access write actions.
- Authenticated write users continue to work normally.
- Session-scoped personalization resets correctly on shared devices.
- When convention mode is disabled, current auth protections still apply.

## Decision Log
Use this section to track scope or contract changes made during implementation.

- 2026-03-15 - Mode/access validation completed in `dev` (manual end-to-end validation).
  - Reason: confirm kiosk guest boot, staff fallback, and role-based access restrictions before convention readiness sign-off.
  - Impact: checklist validation item completed; implementation behavior confirmed against current plan.
  - Follow-up: keep validation rerun as part of final pre-convention release gate.
