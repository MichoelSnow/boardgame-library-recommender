# ADR 0001: Phase 4 Architecture Foundations

## Status
- Accepted

## Context
- `pax_tt_recommender` is moving from a working prototype toward a convention-ready production web app.
- The system must support:
  - short-term convention usage with up to roughly `100` concurrent users
  - a mostly read-heavy traffic profile
  - a smaller set of concurrent writes
  - mobile-heavy usage
  - strong cost sensitivity
- Several architecture choices needed to be made before implementation work could proceed.

## Decision 1: Database Platform
### Options Considered
- Keep SQLite on a Fly volume
- Move to managed Fly Postgres
- Use mixed DB technology between environments

### Tradeoffs
- SQLite is simple and cheap, but weak for concurrent writes and operational scaling.
- Managed Fly Postgres adds migration complexity and cost, but better supports concurrent writes and future growth.
- Mixed DB tech between `dev` and `prod` increases drift and debugging complexity.

### Final Decision
- Migrate to self-managed Postgres on Fly before convention launch.
- Use self-managed Postgres on Fly in both `dev` and `prod`.
- Require local Postgres validation in WSL before `dev` cutover.
- Managed Fly Postgres is rejected for the current build primarily because its fixed monthly cost is too high for the current budget.
- Backup, restore, and DB-health monitoring become explicit responsibilities of this choice.

## Decision 2: Image Delivery
### Options Considered
- Continue direct runtime image loading from BoardGameGeek
- Use Fly-hosted storage
- Use Cloudflare R2 + CDN

### Tradeoffs
- Direct BGG loading is simplest but creates latency and external dependency risk.
- Fly storage keeps infrastructure consolidated but is materially more expensive on current estimates.
- Cloudflare R2 is cheaper on storage and fits the object-storage + CDN delivery model better.

### Final Decision
- Move image delivery to Cloudflare R2 + CDN.
- Store stable image keys/paths, not full provider URLs.
- Use a seeded-cache strategy with:
  - convention/library-relevant games
  - top `10,000` ranked games

## Decision 3: Convention Access Model
### Options Considered
- Require login for all users
- Anonymous public reads for all endpoints
- Controlled anonymous read-only access with authenticated writes

### Tradeoffs
- Login for all users adds friction on shared convention devices.
- Public anonymous access to all endpoints increases exposure and weakens control.
- Controlled anonymous read-only access reduces friction while preserving protection for write paths.

### Final Decision
- Use convention mode with explicit `CONVENTION_MODE` toggle.
- Allow anonymous read-only access only to the approved convention endpoint allowlist.
- Keep write paths authenticated.
- Use session-scoped anonymous state for shared devices.

## Decision 4: Convention Runtime
### Options Considered
- Keep the current cold-start-oriented low-cost profile
- Use a warmed production runtime during convention hours
- Scale aggressively by default without rehearsal

### Tradeoffs
- Cold starts conflict with the convention responsiveness goal.
- A warmed runtime increases cost but reduces startup latency.
- Aggressive scaling without measured validation risks overspending or overcommitting memory.

### Final Decision
- Use a convention runtime profile during active convention hours.
- Initial target:
  - one always-running production machine
  - `Gunicorn` with `2` Uvicorn workers
- Final worker count and memory must be validated by rehearsal in `dev`.

## Decision 5: Observability and Alerting
### Options Considered
- Add centralized log aggregation immediately
- Use Fly logs plus a simple alerting layer
- Delay alerting until after convention launch

### Tradeoffs
- Centralized log aggregation adds complexity and cost.
- Fly logs plus targeted alerting is simpler and cheaper.
- Delaying alerting would leave convention operations too reactive.

### Final Decision
- Use Fly logs as the initial operational log source.
- Do not add dedicated centralized log aggregation in the first convention build.
- Add email alerting before convention launch using:
  - GitHub Actions scheduled workflow as the check runner
  - Resend as the preferred provider
  - SendGrid as the fallback provider

## Decision 6: Frontend Architecture
### Options Considered
- Keep expanding the current component-owned request pattern
- Rewrite the frontend stack
- Keep React and improve the frontend data layer and structure

### Tradeoffs
- Continuing ad hoc request logic increases complexity and drift.
- A framework rewrite is expensive and unnecessary for current needs.
- Improving the API layer and query/cache model addresses the real bottlenecks without a rewrite.

### Final Decision
- Keep React and React Router.
- Add a dedicated frontend API layer under `frontend/src/api/`.
- Adopt React Query (TanStack Query) as the canonical frontend data-fetching and cache layer.
- Treat `GameList.js` as a decomposition target.

## Consequences
- Phase 4 implementation should proceed as isolated major cutovers.
- The Postgres migration is the highest-risk cutover and must preserve SQLite fallback during stabilization.
- The image migration should be shipped separately from the Postgres cutover.
- Convention runtime and access changes should be tested in `dev` rehearsal windows before convention use.
