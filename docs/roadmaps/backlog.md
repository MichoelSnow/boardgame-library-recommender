# Backlog

This file is the canonical home for ad hoc and medium-term roadmap items that were previously tracked in `todo.md`.

## Data
- Download all images into a database for faster serving.
  - Current status: image download script exists; dataset is partially downloaded.
- Precompute recommendations for all games for dialog views.

## UI
- In the dialog, show preferred and best player counts.
- Add in-library indicators to the game details dialog content area.
- Add in-library indicators to similar games shown in the dialog recommendations section.
- Keep game details dialog open when applying dialog-based filters (do not auto-close on filter chip click).
- In game details dialog, show selected-state styling for already-applied filter chips (for example blue chip), and avoid invisible toggle behavior.
- Reset game catalog pagination to page 1 when toggling between `pax_only` and `all board games` to avoid invalid/out-of-range pages (for example page 7020 in all-games -> page 7020 in pax-only).
- Update Board Game Catalog Help Guide content to match current behavior and remove stale guidance.
  - Example stale copy to remove/update: recommendation/session behavior after page refresh.

## Code
- Move to Python 3.12.
- After the Python upgrade, simplify `backend/app/versioning.py` to rely on stdlib `tomllib` only (remove fallback parser path if no longer needed).
- Harden `backend/scripts/migrate_sqlite_to_postgres.py` sequence-reset SQL to quote table identifiers explicitly instead of direct string interpolation.
- Migrate frontend away from legacy CRA (`react-scripts`) dependency chain to a modern build stack.
  - Goals:
    - Reduce transitive npm audit exposure from CRA-era packages.
    - Improve build/test performance and long-term maintainability.
    - Preserve existing app behavior, routing, auth flow, and test coverage.
  - Initial acceptance criteria:
    - `npm run build` and core frontend tests pass on the new stack.
    - CI frontend jobs (`frontend-build`, `frontend-audit`) remain green with revised commands.
    - No regression in local dev workflow documented in `frontend/README.md` and runbooks.

## App
- Allow multiple selection in player count.
- Sort categories and mechanics alphabetically.
- Align categories and mechanics into a fixed grid if possible.
- Add ability to send recommendation lists via email or SMS.
- Add tag search (larger effort).

## Fly.io
- Add redundancy using multiple volumes where feasible.
- Add user activity logging (for example, last login time).

## Notebooks
- Add back `google-api-python-client`, `google-auth-httplib2`, and `google-auth-oauthlib` for `data_pipeline/notebooks/pax_tabletop_library.ipynb`.
