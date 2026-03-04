# Frontend Architecture Plan

## Purpose
- Define the Phase 4 frontend architecture direction for `pax_tt_recommender`.
- Improve maintainability and responsiveness without changing the core React-based stack.

## Scope
- Covers:
  - API layer organization
  - query caching and invalidation
  - frontend state boundaries
  - the direction for refactoring large UI components
- Does not require immediate implementation of the full refactor.

## Service-Level Reference
- Canonical latency and reliability targets are defined in [service_level_targets.md](/home/msnow/git/pax_tt_recommender/docs/policies/service_level_targets.md).
- Frontend data-fetching and cache decisions should support those targets by reducing unnecessary repeated requests and improving perceived responsiveness.

## V1 Architecture Decisions
- Keep React and React Router.
- Do not pursue a frontend framework rewrite.
- Add a dedicated frontend API layer under `frontend/src/api/`.
- Adopt React Query (TanStack Query) as the canonical frontend data-fetching and cache layer.
- Treat `frontend/src/components/GameList.js` as a decomposition target rather than the desired long-term structure.
- Centralize auth/session/convention-mode UI state handling rather than scattering it across large components.

## API Layer Organization
### Target Structure
- Create `frontend/src/api/` modules such as:
  - `games.js`
  - `recommendations.js`
  - `auth.js`
  - `filters.js`
  - later, feature-specific modules such as `librarianPicks.js`

### Responsibilities
- Endpoint path ownership
- Request parameter shaping
- Shared request helpers and consistent error handling
- Any lightweight response normalization needed by the UI

### Non-Goals
- Do not keep adding raw endpoint construction directly inside unrelated UI components.
- Do not duplicate API request logic across multiple components once the API layer exists.

## Query Caching and Invalidation Strategy
### Canonical Query Layer
- Use React Query as the canonical query/caching mechanism for frontend reads.
- Avoid ad hoc repeated `useEffect` + local fetch logic as the long-term pattern.

### Cache Targets
- Filter metadata:
  - cache aggressively
  - long stale time
- Game details:
  - cache per game ID
  - moderate stale time
- Game list queries:
  - cache by query key derived from the current URL-backed filter state
- Recommendation responses:
  - cache by target game and relevant request inputs
  - shorter stale time than static metadata, but still cache within session
- Auth/current user:
  - cache current-user state
  - invalidate on login, logout, and password change

### Invalidation Rules
- Login:
  - invalidate current-user/auth state
- Logout:
  - clear current-user/auth state and any user-specific cached data
- Password change:
  - refresh current-user/auth state as needed
- Filter changes:
  - derive a new game-list query key from the active URL state
- Recommendation inputs changing:
  - derive a new recommendation query key rather than mutating cached results in place

## Component Responsibility Direction
### `GameList.js`
- `GameList.js` is currently carrying too much responsibility.
- It should be progressively split into:
  - URL state parsing/sync
  - query-state derivation
  - list-fetching hook
  - recommendation-mode controller
  - presentation-focused UI sections

### Why This Matters
- Reduces regression risk in a high-change component
- Makes convention-mode behavior easier to integrate cleanly
- Makes future features (for example librarian picks) easier to add without compounding complexity

## Convention-Mode Frontend Implications
- Convention-mode UI differences should be controlled through explicit app-level state/flags.
- Auth-dependent UI logic should be centralized.
- Anonymous session behavior on shared devices should be handled through dedicated session-state logic rather than scattered component-specific workarounds.

## Implementation Sequence
1. Add the `frontend/src/api/` structure and move endpoint logic out of large components.
2. Introduce React Query for the highest-value read paths:
  - filter metadata
  - game list
  - game details
3. Add React Query-based caching for recommendation responses.
4. Refactor `GameList.js` into clearer state/query/presentation boundaries.
5. Centralize auth/session/convention-mode state handling.

## Exit Criteria
- Frontend API request logic has a defined home under `frontend/src/api/`.
- A canonical query/caching layer is selected and documented.
- Cache ownership and invalidation rules are defined.
- The `GameList.js` decomposition direction is explicit enough to guide future implementation.
