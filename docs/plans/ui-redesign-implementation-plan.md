# UI Redesign Implementation Plan

This plan is based on the living specification in [`docs/active/ui-redesign.md`](active/ui-redesign.md). The specification remains authoritative for UX decisions; this document describes a practical implementation sequence and calls out work that cannot begin safely until open design decisions are resolved.

## Current architecture assessment

The main browse experience is implemented in `frontend/src/components/GameList.js`. It currently owns most browse state and behavior: debounced text search, pagination, sorting, library scope, player filtering, weight filtering, mechanic/category selection, active filter chips, game details, and the personalized recommendation transition. It persists search, sort, library scope, players, player recommendation mode, weight, mechanics, and categories through React Router `useSearchParams`.

`GameList` currently renders a permanent search field, a horizontal filter-button row with inline panels, the result count/pagination, existing `GameCard` components, and `GameDetails`. `Navbar` provides the global AppBar, home navigation, help/tour, suggestions, admin access, password controls, and logout. The redesign should therefore narrow the browse-header change to the catalog portion of `GameList` and avoid moving recommendation, card, details, or global account behavior unless a later decision explicitly expands scope.

The frontend query boundary is `frontend/src/hooks/useGameListQueries.js` and `frontend/src/api/games.js`. The catalog request currently sends the existing scalar/CSV filters to `GET /api/games/`; mechanics and categories are loaded independently from `/api/mechanics/` and `/api/categories/`. The backend endpoint in `backend/app/main.py` delegates filtering and sorting to `backend/app/crud.py`. Existing filtering supports search, library scope, player count plus recommended/best modes, weight, mechanics, categories, and the existing sort fields. The data model already contains `max_playtime`, `min_age`, `average_weight`, rank fields, mechanics, categories, and suggested-player rows, but the current game-list API does not expose redesign-specific playtime, age, style, or cooperative parameters.

The maintained test suite is intentionally small. Frontend coverage is concentrated in `GameList.test.js`, the filtering and recommendation flows, and the authentication/admin-route checks. Backend coverage is concentrated in the API contract, security, database configuration, kiosk-token, image-proxy, and degraded-recommendation tests. Do not add tests for deleted legacy paths or for framework behavior that is already covered by MUI, React Router, React Query, or the browser.

## Fixed constraints and non-goals

- Follow the agreed Option A compact toolbar, left drawer, active-chip cap, result-count placement, and existing cards described in the specification.
- Preserve hard-constraint catalog filtering and existing BGG rank/default sort behavior. Do not introduce suitability scoring.
- Preserve personalized recommendation state, like/dislike controls, recommendation API behavior, and recommendation UI. Conventional filters remain disabled in recommendation mode unless a separate decision changes that scope.
- Preserve convention/library-specific behavior, including `library_only` and kiosk behavior.
- Preserve existing expansion behavior: do not exclude expansions by default and do not introduce an expansion filter.
- Preserve the deliberate distinction between tag filtering from details and filtering while already browsing.
- Keep implementation in the existing React/MUI/React Query structure. Do not introduce a new UI framework, global state library, or architectural rewrite.
- Keep the existing game cards and recommendation discoverability outside this effort.

## Prerequisites and decisions before implementation

The following decisions materially affect API contracts or later user-visible behavior and should be resolved before the corresponding phase. Finalized behavior is recorded in the specification. Only decisions needed by the current stage should block implementation:

1. The complete BGG category/mechanic crosswalk, duplicate handling, friendly labels, and source IDs needed by the full searchable lists. Ambiguous classifications must be flagged for review rather than silently resolved; defer this to the taxonomy stages.
2. Final tooltip/help text and accessibility acceptance details; defer wording and the full accessibility review to the relevant implementation stage.

The header navigation and responsive layout decision is recorded in the living specification and is ready for Stage 1. Preserve the existing recommendation-mode filtering behavior; it is not an open decision. Verify the supported sort options directly against the existing `sortOptions` and backend `GameSortField` during implementation rather than treating mockup labels as prerequisites.

### Testing scope for this plan

Keep only tests that protect an essential user workflow, security boundary, API contract, data-integrity rule, or non-obvious state transition. Prefer one focused test or flow for related behavior over separate tests for every control or visual variation.

- Do not add automated tests for static placement, exact copy, MUI primitives, responsive breakpoints, tap-target dimensions, drawer animation, or duplicate legacy paths. Verify visual and responsive behavior manually on the target devices.
- Keep frontend tests focused on state/query changes and critical preserved behavior. Do not add a dedicated automated browser-back test; verify browser/Android Back during the manual mobile review.
- Keep backend tests focused on new contract boundaries, security behavior, and filter combinations that could return incorrect data. Combine related cases where practical instead of creating one test per field or label.
- Run tests only after explicit execution authorization. A full suite, lint run, or CI run is an optional handoff check, not a requirement for every implementation stage.

## Implementation stages

### Stage 1 — Establish the browse-shell seam

Purpose: implement the agreed layout without changing filtering semantics or recommendation behavior.

Tasks:

- [x] Extract the catalog-toolbar responsibilities from `frontend/src/components/GameList.js` into small local components or clearly bounded sections: compact header/search control, toolbar, active chips, filter drawer shell, and sort popover. Keep state ownership in `GameList` initially unless extraction is required for testability.
- [x] Add the compact browse header around the existing `Navbar`/browse content without disturbing global navigation, help, suggestions, admin, password, or logout actions. Make the search icon expand a field that stays open until explicitly closed; clearing removes the query without closing it, closing clears the query and collapses the field, and Enter, keyboard dismissal, and result updates do not close it. Preserve the current debounced query behavior.
- [x] Replace the permanent filter-button row with `Filters` and `Sort` controls. Use the existing sort values and immediately apply selection; non-default sort labels must be visible on the control, and the menu must identify the currently selected option.
- [x] Add the result count directly above the existing results and retain current pagination and responsive `GameCard` rendering.
- [x] Add left-side drawer open/close behavior with approximately 90% phone width and a 420px maximum on larger screens. Support the header X, backdrop tap, and browser/Android Back; keep drawer visibility temporary and out of URL parameters. Keep the fixed drawer header (`Filter Games`, `Clear All`) and scroll only the accordion body. Do not yet rename or add filter semantics that require backend work.
- [x] Keep only the minimal frontend coverage for state-changing browse behavior: search clear/close, sort application, drawer dismissal, and any preserved query behavior not already covered by the existing flows. Verify static placement, result-count presentation, and responsive sizing manually.

Completion conditions: the browse page has the agreed shell at phone, tablet, and desktop breakpoints; existing catalog requests receive the same filter values; recommendation mode and game details still operate through their existing paths; no new backend contract is required for this stage.

### Stage 2 — Migrate existing filters into accordion sections

Purpose: move current filtering controls into the drawer while preserving current query semantics.

Tasks:

- [ ] Implement the default accordion state: Group & Requirements expanded; Game Type and Theme & Setting collapsed. Preserve selections when sections collapse or the drawer reopens.
- [ ] Migrate current Players, Complexity/Weight, mechanics, and categories controls into the drawer, keeping changes immediately applied without a Show Games button.
- [ ] Rename the user-facing Weight control to Complexity and align thresholds with the specification. Resolve the existing boundary mismatch (`crud.py` currently uses beginner `<= 2`, midweight `> 2 and < 4`, heavy `>= 4`) before changing labels or comparisons to the specified Light `< 2`, Medium `2–4` inclusive, Heavy `> 4`.
- [ ] Implement active-filter accounting, prioritized maximum-three chips, `+N more`, whole-chip touch targets, and section-selection counts. Keep sort, search, library scope, and recommendation state distinct from filter chips; Clear All clears only filter constraints.
- [ ] Preserve URL state for all existing filters; do not encode drawer visibility or transient accordion state in URL parameters.
- [ ] Add or adjust one focused flow test only where filter state or URL serialization changes: cover restoration of a meaningful filter selection and recommendation-mode disabling if affected. Verify chip prioritization, collapse/reopen presentation, and touch behavior manually rather than adding a test for each control.

Completion conditions: all currently supported filters work from the drawer with unchanged backend semantics, active selections are discoverable/removable on touch, and existing deep links continue to restore their state.

### Stage 3 — Define and implement the expanded filter contract

Purpose: add only the new hard constraints and unified user-facing taxonomy that the current API cannot represent.

Tasks:

- [ ] Convert the approved decisions into an explicit frontend/backend contract: maximum play time, minimum age, game style, cooperative, featured/full Game Type and Theme selections, OR within each Game Type/Theme group, AND across independent groups, and the separately agreed Complexity multi-selection semantics.
- [ ] Extend the `GET /api/games/` query parameters and the corresponding `backend/app/main.py`, CRUD function, cache-key construction, and API tests. Apply all selected constraints with AND across independent filter groups; implement the decided OR/AND semantics within multi-select taxonomy groups.
- [ ] Use existing `BoardGame` fields and relation tables where possible: `max_playtime`, `min_age`, `average_weight`, `family_games_rank`, `party_games_rank`, category membership, and mechanic membership. Exclude null/zero playtime or age when those constraints are active as specified.
- [ ] Implement the Game Style mappings exactly after approval: family rank, children category membership, and party rank/category union. Add cooperative mechanic matching without presenting absence as “Competitive.” Review the complete BGG crosswalk during this stage and flag ambiguous classifications for developer review rather than silently resolving them.
- [ ] Implement player `9+` and Recommended/Best behavior using existing suggested-player semantics: Allowed matches support at least one count of nine or more; Recommended and Best match the corresponding level at any count of nine or more. Verify how imported rows represent these cases and avoid a new model field unless the existing data cannot support the agreed behavior.
- [ ] Add or extend filter-option API support for full searchable mechanics/categories and any server-side user-facing crosswalk needed to avoid shipping an unmaintainable hard-coded taxonomy. Keep option payloads stable and cacheable.
- [ ] Add focused backend API/CRUD coverage for the new contract's boundary and combination semantics, unknown-value handling, pagination totals, and cache-key separation when caching changes. Combine related cases where practical. Add one frontend flow check for serialization/restored URL state only if the new parameters require it.

Completion conditions: every implemented drawer control maps to a documented API parameter and deterministic hard constraint; invalid/unknown options fail safely or are ignored according to an explicit contract; backend tests demonstrate no cross-filter leakage.

### Stage 4 — Complete featured/full taxonomy UX

Purpose: make the expanded lists useful to casual attendees without duplicating BGG concepts.

Tasks:

- [ ] Add the ten approved featured Game Types and Themes, keeping Set Collection in the full Game Type list and keeping Medieval/World War II and Zombies/Horror separate.
- [ ] Add inline Show All expansion and search for each list, retaining selections while collapsed. Ensure technical/non-featured options remain available in the complete list.
- [ ] Apply the approved friendly-label crosswalk and only add short explanations/tooltips where the terminology needs them. Base explanations on verified BGG definitions rather than name similarity.
- [ ] Perform a manual keyboard and narrow-device smoke check for focus, touch targets, drawer scrolling, accordion behavior, chip removal, and overflow. Add an automated test only if a non-obvious interaction cannot be checked reliably by inspection.

Completion conditions: featured and full lists share one selection state and one backend mapping, selections survive collapse/reopen, and accessibility checks cover the interactive drawer controls.

### Stage 5 — Details navigation, regression verification, and handoff

Purpose: reconcile the redesign with existing navigation and confirm preserved functionality.

Tasks:

- [ ] Update `GameDetails` tag callbacks and `GameList` navigation/state handling so detail-originated category/mechanic selection immediately returns to the list, adds the selected filter without duplicating it, preserves all other active filters, clears search, and applies the updated filters automatically.
- [ ] Verify sort behavior against all current backend-supported values, including default rank and name/rank variants; ensure recommendation sorting remains separate and unchanged.
- [ ] After explicit execution authorization, run only the focused tests for changed behavior and record failures. Full-suite tests, lint, and CI remain optional handoff checks rather than mandatory per-stage work.
- [ ] Review the result on a narrow phone and convention tablet, including kiosk/library scope, filter drawer dismissal/back behavior, no-results states, pagination, and recommendation-mode transition.
- [ ] Update the canonical documentation or the living specification if implementation decisions resolve currently open items; do not duplicate the specification’s full taxonomy in code comments or a second policy document.

Completion conditions: essential browse, details, search, sort, library, filtering, and recommendation workflows have focused regression coverage where their behavior changed; the agreed open decisions are recorded; implementation can ship as one focused PR unless a concrete dependency failure later justifies splitting it.

## Backend/API impact summary

The initial shell and migration stages can be frontend-only. New hard filters cannot be implemented reliably with the current `/api/games/` contract. They will require coordinated changes to:

- `backend/app/main.py` request parameters and sort/filter validation;
- `backend/app/crud.py` query predicates and total-count cache keys;
- likely `backend/app/schemas.py` only if filter-option or game response shapes change;
- `backend/app/models.py` only if inspection proves the existing fields/relations are insufficient (no model change is currently indicated);
- `frontend/src/api/games.js`, `frontend/src/hooks/useGameListQueries.js`, and `frontend/src/components/GameList.js` serialization/state;
- focused backend API/CRUD tests and frontend component/flow tests only where a changed contract or non-obvious state transition requires them.

No recommendation endpoint or recommender model change is required by the current specification.

## Technical risks and dependencies

- `GameList.js` currently combines many responsibilities; an overly broad rewrite could regress recommendation transitions, URL synchronization, or details callbacks. Extract only after behavior is covered.
- The current backend uses CSV IDs and requires all selected mechanics/categories (`HAVING count == len(...)`), so changing taxonomy or multi-select semantics without an explicit contract can silently alter results.
- Existing complexity thresholds do not match the specification’s provisional boundaries. Labels must not be changed independently of predicate decisions.
- Adding parameters requires updating the total-count cache key; otherwise different filter combinations can receive stale totals.
- Full taxonomy option loading may be large. Prefer cached existing endpoints or a small server-provided crosswalk, and avoid a new search service unless measured UX requires it.
- URL state, drawer history, Android Back, and detail-originated navigation are coupled. Keep drawer visibility out of URL state and ensure browser/Android Back closes the temporary drawer UI.
- Library scope and recommendation mode are separate from catalog filters. The drawer’s Clear All must clear only filter constraints and must preserve search, sorting, library scope, liked/disliked games, and recommendation state.
- The specification’s BGG classifications are intentionally imperfect and based on an older snapshot. Do not hard-code snapshot counts or infer permanent thresholds from them.

## Open questions requiring developer decisions

The implementation should not silently decide the following: the complete BGG crosswalk and option ownership, or tooltip wording/accessibility acceptance. These remain open in `docs/active/ui-redesign.md` and should be resolved before their dependent taxonomy and accessibility work begins. Header navigation and responsive treatment are decided; recommendation-mode filtering remains unchanged; and sort choices should be verified from the existing code.
