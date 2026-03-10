# Migration Cutover Strategy

## Purpose
- Define the cross-cutting sequencing, cutover, and rollback rules for major architecture changes.
- Prevent rollback ambiguity by keeping major migrations isolated and staged.

## Scope
- Applies to the current major architecture workstreams:
  - Postgres migration
  - image storage migration
  - convention mode access changes
  - convention runtime profile changes

## Core Rule
- Do not combine multiple major cutovers into the same release event.
- Each major cutover must complete its own:
  - implementation
  - `dev` validation
  - `prod` validation
before the next major cutover begins.

## Rollback Complexity Classification
### Low / Config-Reversible
- Convention runtime profile
  - rollback path:
    - revert runtime configuration to the normal non-convention profile
- Convention mode access
  - rollback path:
    - disable `CONVENTION_MODE`
    - return to the standard authenticated model

### Medium / Mostly Config-Reversible
- Image storage migration
  - rollback path:
    - revert image resolution to the prior source/path behavior
    - preserve placeholder behavior as the safe fallback
  - note:
    - image delivery is user-facing but not transactional primary data

### High / Data-Migration Reversible Only By Fallback
- Postgres migration
  - rollback path:
    - switch application config back to the preserved SQLite-backed path
    - redeploy the last known-good SQLite-backed release
  - note:
    - this is a service-recovery rollback path, not a bidirectional data-reconciliation strategy

## Fallback Preservation Rules
- Do not remove fallback paths until the replacement path is validated and stable.
- For the current migration tracks, this means:
  - keep SQLite intact during Postgres stabilization
  - keep the backup image-resolution path available until Fly-local delivery is proven stable in both `dev` and `prod`
  - keep normal non-convention auth mode available via configuration
  - keep the normal non-convention runtime profile available

## Postgres-Specific Risk Note
- Once production accepts writes on Postgres, rolling back to SQLite may lose post-cutover writes unless additional synchronization tooling exists.
- Because of that:
  - Postgres rollback should be treated as a service-recovery mechanism
  - not a zero-loss bidirectional rollback
- The initial production Postgres cutover should therefore be staged carefully and validated quickly.

## Recommended Cutover Order
- The safest rollback order does not always match the dependency order, so use this rule:
  - sequence work by dependency first
  - isolate high-risk cutovers operationally
- Practical order:
  1. Convention runtime profile (low-risk, config-reversible)
  2. Convention mode access (config-reversible)
  3. Postgres migration (highest-risk, staged carefully)
  4. Image storage migration (medium-risk, user-facing but non-transactional)

## Validation Gate For Each Major Cutover
For every major cutover:
1. Complete implementation.
2. Deploy to `dev`.
3. Run the relevant automated validation.
4. Run required targeted manual checks.
5. Promote to `prod`.
6. Validate `prod`.
7. Only then begin the next major cutover.

## Required Decision Discipline
- Do not retire the old path just because the new path deployed successfully once.
- Do not treat “rollback exists” as meaning “rollback is cheap.”
- Document the exact fallback and validation path before shipping each major cutover.

## Exit Criteria
- Each major workstream has:
  - a defined rollback type
  - a preserved fallback path where needed
  - an isolated cutover window
  - a validation checkpoint before the next major cutover
