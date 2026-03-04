# Image Storage Migration Plan

## Purpose
- Define the migration away from direct runtime image loading from BoardGameGeek.
- Move toward a controlled image-delivery path using object storage plus CDN.

## Goals
- Reduce latency for mobile-heavy usage.
- Remove runtime dependency on BoardGameGeek for normal image delivery.
- Improve reliability during convention usage.
- Use a cost-efficient object storage provider for image delivery.

## Service-Level Reference
- Canonical performance, reliability, and recovery targets are defined in [service_level_targets.md](/home/msnow/git/pax_tt_recommender/docs/policies/service_level_targets.md).
- This migration must support the image-delivery target and remain aligned with the overall convention-hour reliability and recovery targets.

## Cutover Strategy Reference
- Cross-cutting sequencing and rollback rules are defined in [migration_cutover_strategy.md](/home/msnow/git/pax_tt_recommender/docs/architecture/migration_cutover_strategy.md).
- This migration should be shipped as its own major cutover, not combined with the Postgres cutover.

## Non-Goals
- Do not store images in the relational database.
- Do not require the provider choice to be finalized before documenting the migration plan.

## Target Architecture
- Store image assets in object storage.
- Serve them through a CDN.
- Target provider:
  - Cloudflare R2
- Delivery model:
  - Cloudflare R2 object storage plus CDN delivery
- Store stable image keys/paths in app data, not full provider URLs.
- Preferred key format:
  - `games/<bgg_id>.<ext>`

## Current State
- The app currently depends on BoardGameGeek-hosted image URLs at runtime.
- This adds:
  - extra latency
  - external dependency risk
  - less predictable performance during heavy use

## Failure Policy
- Final-state runtime behavior should not depend on BoardGameGeek for image delivery.
- If an image is missing after cutover, the app should render a local placeholder image rather than a broken image or a runtime fallback to BoardGameGeek.
- The placeholder should:
  - keep the same card aspect ratio and layout
  - avoid broken-image icons
  - optionally display subtle "Image unavailable" messaging

## Key Design Decisions
- Key images by BoardGameGeek game ID where possible.
- Keep the image layer independent from the relational DB migration.
- Do not combine this migration with the Postgres cutover in one step.
- Treat this as a deliberate Phase 4 cutover effort, not an indefinite hybrid state.
- Store only the image key/path in app data; construct the full provider/CDN URL from configuration.

## Migration Sequence
1. Create the Cloudflare R2 bucket and define the public/CDN URL pattern.
2. Define the canonical storage key format (preferably based on BGG ID).
3. Build the bulk image-download pipeline for the seeded initial catalog.
4. Seed Cloudflare R2 with:
   - all convention/library-relevant games
   - the top `10,000` games across ranked lists (accepting overlap between lists)
5. Build a single image-sync script that:
   - checks whether a game is library-relevant, or
   - checks whether a game is in the top `10,000` ranked set,
   - and downloads/uploads the image if it qualifies and is missing
6. Trigger that image-sync script from the import/update path so it handles:
   - newly added qualifying games
   - games that newly become library-relevant
   - games whose rank rises into the top `10,000`
7. Update the app to resolve images from the new storage path using stored image keys/paths.
8. Validate coverage, latency, cache-miss behavior, and placeholder behavior in `dev`.
9. Cut production over to the Cloudflare R2-backed image-delivery path.

## Operational Constraints
- The migration should prioritize mobile performance.
- The migration should minimize new ongoing cost where possible.
- The migration should be validated in `dev` before production cutover.
- The implementation should assume Cloudflare R2 unless a later cost or operational constraint forces re-evaluation.
- The initial cutover does not require a full all-games backfill; the seeded catalog plus controlled cache-fill path is the target.

## Cost Analysis (Current Planning Estimate)
- Current catalog size:
  - `168,475` games
- Image-size estimate source:
  - local image files for ranked games `1..100`
  - `98 / 100` images present locally
- Observed sample statistics:
  - mean image size: `770,913` bytes (`752.85 KiB`)
  - standard deviation: `854,336` bytes (`834.31 KiB`)
- Estimated total storage footprint for `168,475` games using the observed mean:
  - `129,879,638,434` bytes
  - `129.88 GB` (decimal)
  - `120.96 GiB` (binary)
- Estimated monthly storage cost using this sample-based mean:
  - Fly storage at `$0.15 / GB-month`: about `$19.48 / month`
  - R2 storage at `$0.015 / GB-month`: about `$1.95 / month`
- Interpretation:
  - R2 is about `10x` cheaper on storage alone under this estimate
  - storage-only pricing is not the whole decision; request/egress/CDN behavior still matter
  - despite that caveat, Cloudflare R2 is the chosen target provider for Phase 4 planning based on current cost direction
- Sample caveat:
  - this estimate is based on a top-100 ranked-game sample, not the full corpus
  - the top-ranked sample may overrepresent larger images, so final all-catalog sizing should be verified before provider selection

## Validation Criteria
- Most requested images resolve from the new storage path.
- BoardGameGeek is used only as a controlled cache-fill origin on R2 misses, not as the normal client-facing image source.
- Missing images fall back to the local placeholder cleanly.
- First meaningful image is visible within the target `1500 ms` budget under representative convention conditions.
- Broken-image rates are acceptable before final cutover.

## Seeded Cache Strategy
- Initial preload target:
  - all convention/library-relevant games
  - top `10,000` games from ranked lists
- Because the ranked lists overlap, the actual seeded image count will be lower than a naive additive count.
- This reduces:
  - initial migration time
  - initial storage footprint
  - upfront download volume
- The long tail should be filled by the controlled cache-miss ingestion path over time.

## Cache-Miss Policy
- Prefer a non-blocking cache-miss policy in V1:
  - if an image is missing from R2 at request time, render the local placeholder
  - record/log the miss for follow-up ingestion
- Do not make the main user-facing request path wait on a synchronous BoardGameGeek fetch in the first implementation.
- This keeps request latency predictable and avoids coupling page-render latency to third-party image fetches.
- If synchronous cache fill is ever added later, it should include explicit duplicate-fill protection for the same image key.
