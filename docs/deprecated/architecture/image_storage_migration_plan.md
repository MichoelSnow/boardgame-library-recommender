# Image Storage Migration Plan

## Purpose
- Define image delivery architecture that avoids direct client/runtime dependency on BoardGameGeek for normal operation.
- Keep the convention path fast, reliable, and operationally simple.

## Current Status (2026-03-09)
- `dev` has been updated and validated on the Fly-local image model.
- `prod` has not been changed yet by design.
- Production cutover is intentionally deferred until:
  1. changes are merged to `main`
  2. `main` is deployed to `prod`
  3. production image seeding is executed and validated

## Goals
- Reduce card-grid image latency.
- Keep image delivery resilient during convention usage.
- Minimize moving parts and recurring infrastructure cost.
- Preserve a rollback path if the primary model regresses.

## Service-Level Reference
- Canonical performance/reliability/recovery targets: [service_level_targets.md](../policies/service_level_targets.md).

## Cutover Strategy Reference
- Cross-cutting sequencing and rollback rules: [migration_cutover_strategy.md](migration_cutover_strategy.md).

## Non-Goals
- Store images in relational DB tables.
- Make image migration dependent on Postgres migration sequencing.

## Active Target Architecture
- Primary runtime model (`dev`, planned for `prod`):
  - `IMAGE_BACKEND=fly_local`
  - image files on app volume under `/data/images`
- Storage layout:
  - originals: `/data/images/games/<bgg_id>.<ext>`
  - thumbnails: `/data/images/thumbnails/<bgg_id>.webp`
- Client behavior:
  - catalog cards prefer thumbnail path first
  - details view prefers original path
- Cache-fill behavior:
  - `/api/images/{game_id}/cached?image_url=<origin-url>` can fill missing originals and generate thumbnail sidecar

## Design Decisions
- Keep stable keying by BGG ID (`games/<bgg_id>.<ext>`).
- Keep thumbnails as a sidecar (`thumbnails/<bgg_id>.webp`) while retaining originals.
- Prefer Fly-local serving for primary runtime simplicity/perf.

## Migration Sequence (Primary Path)
1. Implement and validate Fly-local image serving in `dev`.
2. Seed `dev` volume images using BGG-origin sync.
3. Validate image performance and placeholder behavior in `dev`.
4. Merge to `main`.
5. Deploy `main` to `prod`.
6. Seed `prod` image volume (BGG-origin sync).
7. Run production validation.
8. Keep BGG -> Fly reseed commands documented for operational fallback.

## Validation Criteria
- Catalog cards load via thumbnail path without broken-image icons.
- Details view loads originals correctly.
- Missing images resolve to placeholder cleanly.
- Image operations are documented in one operational runbook.
- Production cutover follows dev-first promotion discipline.

## Operations Reference
- Canonical commands and procedures: [image_storage_operations.md](../runbooks/image_storage_operations.md).
