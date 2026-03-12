# API Versioning and Deprecation Policy

## Purpose
- Define how API changes are versioned and how breaking changes are handled.
- Keep the policy simple and realistic for a pre-`1.0` single-developer application.

## Current State
- The app currently exposes endpoints under `/api`.
- There is no parallel `/api/v1`, `/api/v2`, or long-lived multi-version support.
- The frontend and backend ship together and are controlled in the same repo.

## Versioning Policy
- Before `1.0.0`, the backend API should remain a single active version under `/api`.
- Breaking API changes are allowed only when:
  - they are deliberate
  - the frontend is updated in the same change/release
  - tests and docs are updated accordingly
- Do not introduce parallel maintained API versions in the pre-`1.0` phase unless a real external-client requirement appears.

## Compatibility Window
- Current compatibility window:
  - the deployed frontend and deployed backend must remain compatible within the same release
- There is no promise of long-lived backward compatibility for older frontend builds or external clients before `1.0.0`.

## Deprecation Policy
- If an endpoint, parameter, or field is planned for removal:
  1. document the change in the relevant planning or release docs
  2. update the frontend in the same release path
  3. remove the old behavior only when the new behavior is already live and validated
- Avoid long-lived deprecated parallel code paths unless there is a concrete migration need.

## Trigger For Formal Versioning
- Introduce explicit API versioning (for example `/api/v1`) only if one of the following becomes true:
  - you have external clients that are not deployed together with the frontend
  - multiple independently maintained clients need a compatibility window
  - you need to support a staged migration where one release cannot update all consumers together

## Sunset Process (If Formal Versioning Is Added Later)
- If explicit API versions are introduced later, the sunset process should include:
  - a named replacement version
  - a documented sunset date
  - release-note visibility
  - a compatibility window long enough for active clients to migrate

## Practical Rule
- For the current project phase:
  - keep one active API contract
  - ship coordinated frontend/backend contract changes together
  - use deliberate release validation instead of maintaining multiple API versions
