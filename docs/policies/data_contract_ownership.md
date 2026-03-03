# Data Contract Ownership

## Purpose
- Define who owns the API and data contract decisions between backend and frontend.
- Prevent schema drift, undocumented field changes, and accidental frontend/backend mismatches.

## Scope
- Applies to:
  - API response fields
  - API request parameters
  - query parameter names and allowed values
  - auth payloads
  - recommendation endpoint response shape
  - frontend assumptions about backend field names and semantics

## Ownership Model
- Backend schema and API contract are the canonical source of truth.
- Frontend integration must conform to the backend contract.
- In this repo, you are the owner of both sides, but the enforcement rule is:
  - backend contract changes must be deliberate
  - frontend must be updated to match
  - docs and tests must be updated when the contract changes

## Canonical Sources
- Backend models and schemas define the source contract:
  - `backend/app/models.py`
  - `backend/app/schemas.py`
- API endpoint behavior and accepted params are defined in:
  - `backend/app/main.py`
  - relevant backend CRUD/service modules
- Frontend should consume the contract through:
  - a dedicated API layer under `frontend/src/api/`
  - not by scattering undocumented assumptions across components

## Decision Rules
### When changing backend fields or response shape
1. Treat the backend contract as an intentional change.
2. Update:
- backend schemas and endpoint logic
- frontend API layer / consumers
- tests covering the affected contract
- docs if the public behavior changed
3. Do not rely on implicit compatibility if field names or semantics change.

### When changing frontend behavior
1. Do not silently reinterpret backend fields in UI code.
2. If frontend needs a different field shape or meaning:
- change the backend contract intentionally, or
- add explicit frontend transformation in the API layer
3. Do not let one-off component logic become the de facto contract.

## Compatibility Rule
- The backend contract is authoritative, but breaking changes should still be deliberate and tracked.
- Before changing field names, parameter names, or response shape:
  - identify affected frontend flows
  - update or stage those changes together
- Avoid “backend changed, frontend catches up later” for active production paths.

## Documentation Rule
- If a contract change affects user-visible behavior or integration assumptions:
  - update the relevant planning/runbook docs
  - update the frontend architecture plan if the API-layer assumptions change
- Keep this file as the policy document, not a field-by-field reference.

## Testing Rule
- Contract changes require:
  - backend tests for the changed behavior
  - frontend updates for affected consumers
  - smoke validation of the affected user flow
- Prefer catching contract mismatches in tests rather than discovering them in manual deploy validation.

## Practical Single-Developer Interpretation
- You own both backend and frontend integration.
- In practice, this means:
  - backend changes are not “done” until the frontend and tests are updated
  - frontend work should not invent new contract assumptions outside the documented backend behavior

## Exit Criteria
- Backend contract authority is explicit.
- Frontend integration responsibilities are explicit.
- Contract changes have a documented update rule across code, tests, and docs.
