# Docs Index

## Directory Layout
- `roadmaps/`
  - phased engineering work, launch checklists, and feature planning
- `policies/`
  - canonical rules, targets, and ownership documents
- `architecture/`
  - subsystem plans, migration plans, and cutover strategy
- `runbooks/`
  - operational procedures to execute and validate changes
- `adr/`
  - durable architecture decisions and tradeoffs

## Start Here
- [Repo Usage Guide](runbooks/repo_usage_guide.md)
  - practical setup, local run, pipeline, import, and validation command paths
- [Image Storage Operations](runbooks/image_storage_operations.md)
  - canonical dev/prod image import, count, and storage operations
- [Command Reference](runbooks/command_reference.md)
  - quick command lookup for frequent operational and validation tasks
- [Best Practices Migration Guide](roadmaps/best_practices_migration_guide.md)
  - master engineering checklist and phase tracking
- [Pre-Convention Readiness Checklist](roadmaps/pre_convention_readiness_checklist.md)
  - launch gate for convention readiness
- [Deploy Rollback Runbook](runbooks/deploy_rollback_runbook.md)
  - deployment, validation, promotion, and rollback procedure

## Suggested Reading Order
1. [Best Practices Migration Guide](roadmaps/best_practices_migration_guide.md)
   - current roadmap, phase status, and execution order
2. [Repo Usage Guide](runbooks/repo_usage_guide.md)
   - practical day-to-day run and validation commands
3. [Pre-Convention Readiness Checklist](roadmaps/pre_convention_readiness_checklist.md)
   - what must be finished before the convention
4. Canonical policy docs, as needed:
   - [Service Level Targets](policies/service_level_targets.md)
   - [Data Contract Ownership](policies/data_contract_ownership.md)
   - [API Versioning and Deprecation Policy](policies/api_versioning_policy.md)
   - [Observability and Alerting Plan](architecture/observability_alerting_plan.md)
5. Architecture and migration plans for the specific workstream you are implementing
6. [Deploy Rollback Runbook](runbooks/deploy_rollback_runbook.md)
   - when you are executing a deploy, promotion, or rollback

## Canonical Sources
These files should be treated as the single source of truth for their topic. Other docs should reference them instead of restating the same content.

- [Best Practices Migration Guide](roadmaps/best_practices_migration_guide.md)
  - owns engineering migration phases, sequencing, and completion tracking
- [Pre-Convention Readiness Checklist](roadmaps/pre_convention_readiness_checklist.md)
  - owns convention launch-critical tasks
- [Feature Roadmap](roadmaps/feature_roadmap.md)
  - owns non-essential product feature planning
- [Service Level Targets](policies/service_level_targets.md)
  - owns canonical latency, reliability, recovery, and data-loss targets
- [Observability and Alerting Plan](architecture/observability_alerting_plan.md)
  - owns logging source, alert classes, and alert delivery approach
- [Data Contract Ownership](policies/data_contract_ownership.md)
  - owns backend/frontend contract authority and update rules
- [API Versioning and Deprecation Policy](policies/api_versioning_policy.md)
  - owns API versioning, compatibility, and sunset rules
- [Architecture Decision Records](adr/README.md)
  - owns durable architecture decisions and tradeoffs
- [Deploy Rollback Runbook](runbooks/deploy_rollback_runbook.md)
  - owns operational run procedures
- [Engineering Guide](policies/engineering_guide.md)
  - owns repo-wide engineering expectations
- [Repository Structure Policy](policies/repository_structure_policy.md)
  - owns top-level layout boundaries and artifact/notebook placement rules

## Architecture and Migration Plans
These docs describe specific Phase 4 architecture decisions and implementation plans. They should inherit targets and launch priorities from the canonical docs above.

- [Postgres Migration Plan](architecture/postgres_migration_plan.md)
  - relational DB migration from SQLite to self-managed Postgres on Fly
- [Image Storage Migration Plan](architecture/image_storage_migration_plan.md)
  - image-delivery migration history and architecture decisions
- [Convention Mode Access Plan](architecture/convention_mode_access_plan.md)
  - access model for anonymous read-only convention use and authenticated writes
- [Convention Runtime Policy](architecture/convention_runtime_policy.md)
  - warm-runtime policy and rehearsal model for convention hours
- [Frontend Architecture Plan](architecture/frontend_architecture_plan.md)
  - frontend API-layer, caching, and component-structure direction
- [Migration Cutover Strategy](architecture/migration_cutover_strategy.md)
  - sequencing, cutover isolation, and rollback-complexity rules
- [Fly Environment Strategy](architecture/fly_environment_strategy.md)
  - dev/prod environment strategy and Fly-specific operational choices

## Update Rules
- If you are changing a threshold:
  - update [Service Level Targets](policies/service_level_targets.md)
  - only update other docs if their local implications change
- If you are changing phase status or engineering sequencing:
  - update [Best Practices Migration Guide](roadmaps/best_practices_migration_guide.md)
- If you are changing what must be done before convention:
  - update [Pre-Convention Readiness Checklist](roadmaps/pre_convention_readiness_checklist.md)
- If you are adding or reprioritizing non-essential product features:
  - update [Feature Roadmap](roadmaps/feature_roadmap.md)
- If you are changing deployment or incident procedures:
  - update [Deploy Rollback Runbook](runbooks/deploy_rollback_runbook.md)
- If you are changing a subsystem implementation plan:
  - update the relevant architecture/migration plan doc
  - do not duplicate shared targets or launch criteria already owned elsewhere
