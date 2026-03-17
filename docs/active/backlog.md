# Backlog

This is the single active feature backlog.  
If an item becomes launch-critical, move it into `pre_convention_readiness_checklist.md`.

## Product and UX
- [x] Show preferred/best player counts in game dialog.
- [x] Add in-library indicators to the game details dialog content area.
- [ ] Add in-library indicators to similar games shown in the dialog recommendations section.
- [x] Keep dialog open when dialog filters are applied.
- [x] Show selected-state styling for already-applied filter chips and avoid invisible toggle behavior.
- [x] Reset catalog pagination to page 1 when toggling `library_only` vs all-games.
- [ ] Update Board Game Catalog Help Guide to match current behavior.
- [ ] Add tag search (larger effort; likely requires query/index review).
- [ ] Add optional recommendation sharing via email/SMS (requires abuse/rate-limit controls).
- [ ] Allow multiple selection in player count.
- [x] Close open sorting/filter panels when toggling "Show Recommendations" ON.
- [ ] Add the powered by BGG icon to the site (https://boardgamegeek.com/using_the_xml_api)
- [ ] Give the search bar the ability to search description via dropdown option.
- [x] Remove unnecessary/redundant hover hints from UI elements.
  - Game dialog chips, e.g., Designers, artists
  - Sort/filter buttons
- [x] Rename reset filters button to clear all to make it clearer what the button does.
- [x] Add x button to clear search input
- [x] Add x to individual filters when they have information so that users can quickly clear them individually

## Admin and Operations Features
- [x] Build admin console for convention operations.
  - Initial scope: theme color switch, user management, Library CSV upload/validation.
    - #904799 (unplugged)
    - #D9272D (east)
    - #007DBB (west)
    - #F4B223 (aus)
- [] Add ability to name the Library/Convention.  This should affect things like the Navbar, Help dialog, and other UI elements.
- [ ] Add librarian picks workflow.
  - V1: unordered list CRUD for librarian accounts, read for all users.
- [ ] Add user activity logging (for example last login time).
  - Keep retention/privacy handling aligned with `docs/core/security.md`.
- [ ] Add ability to delete imported libraries.   

## Data and Recommendation System
- [ ] Precompute recommendations for all games for dialog views.
  - Preserve degraded-mode behavior when precompute artifacts are missing.

## Platform and Tooling
- [x] Move runtime target to Python 3.13.
- [ ] After Python upgrade, simplify `backend/app/versioning.py` to stdlib `tomllib`.
- [ ] Harden `backend/scripts/migrate_sqlite_to_postgres.py` sequence reset SQL by quoting table identifiers.
- [ ] Migrate frontend from CRA (`react-scripts`) to modern build stack while keeping behavior and CI parity.

## Infrastructure
- [ ] Evaluate Fly redundancy options (multi-volume or equivalent).
  Start with cost/complexity assessment before implementation.

## Notebooks
- [ ] Restore Google auth client dependencies for `data_pipeline/notebooks/library_tabletop_catalog.ipynb`.
