# Convention Mode Access Plan

## Purpose
- Define how the app should behave during convention operation when read-only access is needed on controlled public devices.
- Separate anonymous read-only access from authenticated write access.
- Preserve lightweight personalization for shared devices without requiring account creation.

## Goals
- Allow read-only convention users to access the app without login.
- Keep write actions authenticated and limited to approved users.
- Support session-scoped anonymous personalization on shared/public devices.
- Keep the convention mode simple to enable and disable operationally.

## Non-Goals
- Do not introduce anonymous account creation in the short term.
- Do not make convention mode the default outside event windows.
- Do not use login as the primary abuse-protection mechanism for anonymous read traffic.

## Activation Model
- Convention mode should be controlled by a manual environment flag.
- Initial implementation target:
  - `CONVENTION_MODE=true` enables convention mode
  - `CONVENTION_MODE=false` (or unset) disables it
- This should be applied as an explicit deployment/configuration change before and after convention operation.

## Access Model
### Anonymous Read-Only Users
- Allowed during convention mode only.
- Intended for controlled public devices in the short term.
- No login required.
- Allowed capabilities should include:
  - browse/search/filter the catalog
  - view game details
  - view recommendations
  - view public user-curated recommendation lists (for example librarian picks)
  - use temporary personalization within the current session
- Anonymous users should not be allowed to submit suggestions in V1.
- Anonymous users should have access only to an explicit allowlist of user-facing read endpoints required for these flows.

### Authenticated Write Users
- Must continue to log in even during convention mode.
- Intended for library-team members using their own devices.
- Write access includes:
  - existing authenticated write features
  - future user-curated recommendation list management
- User-curated recommendation lists (for example librarian picks) should remain visible to all users, not only in convention mode.

## Anonymous Personalization Model
- Short-term implementation should use browser `sessionStorage`.
- Reason:
  - the devices are shared/public
  - state should last for the active browser session only
  - local persistence across users is not desirable
- Candidate session-scoped state:
  - liked/disliked selections
  - current recommendation workflow state
  - other temporary read-only personalization relevant to recommendations

## Shared Device Safety Requirements
- Provide a clear "Reset Session" or equivalent control to clear anonymous state quickly.
- Ensure anonymous session state is not stored durably across device users in the short term.
- Avoid `localStorage` for anonymous personalization on shared devices unless there is a specific reason and explicit clearing logic.
- Add automatic session clearing after `3` minutes of inactivity in addition to the explicit reset control.

## Security and Abuse Considerations
- Convention mode is not a substitute for network-edge protection.
- Do not rely on login to mitigate abuse from anonymous read traffic.
- Separate abuse-protection controls should be evaluated for the public read surface, including:
  - rate limiting
  - edge protection / WAF-style controls
  - caching of hot read endpoints

## API Design Implications
- Read endpoints should be reviewed and classified as:
  - safe to expose anonymously during convention mode
  - still requiring authentication
- Do not treat "all read endpoints" as automatically public; use an explicit allowlist of user-facing read endpoints required for convention use.
- The short-term allowlist should include the UI-facing read routes needed for:
  - catalog browsing/filtering
  - game details
  - recommendations
  - public user-curated recommendation lists
- Write endpoints must continue to enforce authentication regardless of convention mode.
- Suggestion submission should remain authenticated in V1.
- Convention-mode checks should be explicit and testable.

## Initial Anonymous Read Allowlist
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

## Convention Mode Enforcement
- Prefer explicit route-level dependency / endpoint classification over broad middleware in the first implementation.
- Reason:
  - easier to audit
  - easier to test
  - lower risk of accidentally exposing endpoints that were not intended to be public

## Implementation Sequence
1. Add a `CONVENTION_MODE` config flag.
2. Implement the explicit anonymous-read allowlist for convention mode.
3. Keep write/admin endpoints authenticated.
4. Add client-side `sessionStorage` support for anonymous personalization.
5. Add an explicit reset-session control.
6. Add auto-clear behavior after `3` minutes of inactivity.
7. Test both:
- convention mode enabled
- convention mode disabled

## Validation Criteria
- Anonymous users can use approved read flows without login when convention mode is enabled.
- Anonymous users cannot access write actions.
- Authenticated write users continue to work normally.
- Session-scoped personalization resets correctly on shared devices.
- When convention mode is disabled, current auth protections still apply.
