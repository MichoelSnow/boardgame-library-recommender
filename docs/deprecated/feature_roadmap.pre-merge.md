# Feature Roadmap

## Purpose
- Track product features and UX improvements that are valuable but are not part of the core engineering migration checklist.
- Separate feature planning from:
  - the engineering migration roadmap
  - the pre-convention launch gate
  - ad hoc scratch notes

## Usage
- Use this document for planned features, enhancements, and product ideas.
- If a feature becomes launch-critical, copy it into [pre_convention_readiness_checklist.md](pre_convention_readiness_checklist.md) and track the execution steps there.
- Keep [best_practices_migration_guide.md](best_practices_migration_guide.md) focused on engineering modernization, not feature scope.

## Priority Legend
- `Now`: important soon, but not currently a launch blocker
- `Next`: useful after core readiness and stability work
- `Later`: backlog / exploratory

## Planned Features

### Librarian Picks
- Priority:
  - `Next`
- Summary:
  - allow authenticated library-team users to maintain their own recommended game lists
  - allow all users to browse those lists
- Current scope assumption for V1 of the feature:
  - library-team users can add/remove games from their own list
  - all users can view librarian lists
  - no explicit ordering in the first implementation
- Why it matters:
  - adds curated human recommendations beyond algorithmic recommendations
  - increases app value during convention use
- Architectural implications:
  - introduces concurrent writes
  - supports the decision to move to Postgres
- Not currently required for:
  - Phase 4 migration completion
  - convention launch readiness unless explicitly promoted into launch scope
- When promoted into implementation planning, create:
  - endpoint/data-model checklist
  - UI flow checklist
  - validation/test checklist

### Future Candidate Features
- [ ] Decide whether to add account-backed persistence for non-anonymous users after convention launch.
- [ ] Decide whether anonymous sessions should support shareable or recoverable recommendation state.
- [ ] Consider richer recommendation workflows after core performance and stability work is complete.
- [ ] Consider librarian-list ordering/ranking only after the unordered list version proves useful.

### Admin Console
- Priority:
  - `Now`
- Summary:
  - add a dedicated admin panel for convention operations and content/runtime controls
- Initial capability targets:
  - switch convention primary color theme from approved palette
  - create/manage users
  - upload and validate PAX game IDs CSV
  - extend with additional operational controls after V1
- Convention palette baseline:
  - `#904799`
  - `#D9272D`
  - `#007DBB`
  - `#F4B223`
  - current next-convention primary target: `#D9272D`
- Launch-critical note:
  - This feature is convention-critical and must be tracked in [pre_convention_readiness_checklist.md](pre_convention_readiness_checklist.md) until complete.

## Intake Rule
- Before starting a new feature implementation, add it here with:
  - summary
  - priority
  - why it matters
  - whether it is launch-critical or deferred
