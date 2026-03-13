# Deploy and Rollback Runbook

This runbook has been split into focused documents for easier navigation.
No operational content was removed; all original sections are mapped below.

## Runbook Map
- Core policy and prerequisites:
  - [deploy_policy_and_prereqs.md](/home/msnow/git/bg_lib_recommender/docs/runbooks/deploy_policy_and_prereqs.md)
- Fly stack lifecycle and DB runtime behavior:
  - [fly_stack_operations.md](/home/msnow/git/bg_lib_recommender/docs/runbooks/fly_stack_operations.md)
- Convention runtime profile and rehearsal guidance:
  - [convention_runtime_runbook.md](/home/msnow/git/bg_lib_recommender/docs/runbooks/convention_runtime_runbook.md)
- Dev deployment and validation:
  - [deploy_dev_runbook.md](/home/msnow/git/bg_lib_recommender/docs/runbooks/deploy_dev_runbook.md)
- Prod promotion, alerting, fallback deploy, and smoke checks:
  - [deploy_prod_runbook.md](/home/msnow/git/bg_lib_recommender/docs/runbooks/deploy_prod_runbook.md)
- Rollback, deploy traceability record, and inspection queries:
  - [rollback_runbook.md](/home/msnow/git/bg_lib_recommender/docs/runbooks/rollback_runbook.md)

## Original Section Mapping (Lossless)
- Purpose -> `deploy_policy_and_prereqs.md`
- Deployment Policy -> `deploy_policy_and_prereqs.md`
- Versioning Policy (+ increment, bump, tagging, release notes rules) -> `deploy_policy_and_prereqs.md`
- Preconditions -> `deploy_policy_and_prereqs.md`
- Quick Wake Commands -> `fly_stack_operations.md`
- One-Time DB App (Re)Bootstrap Notes -> `fly_stack_operations.md`
- DB Keepalive (App-Driven) -> `fly_stack_operations.md`
- Convention Runtime Profile -> `convention_runtime_runbook.md`
- Deploy to Dev -> `deploy_dev_runbook.md`
- Validate Dev (After Every Successful Merge to main) -> `deploy_dev_runbook.md`
- Promote to Prod (Default) -> `deploy_prod_runbook.md`
- Periodic Prod Alerting -> `deploy_prod_runbook.md`
- Local Emergency Fallback Deploy -> `deploy_prod_runbook.md`
- Post-Deploy Smoke Checks -> `deploy_prod_runbook.md`
- Rollback -> `rollback_runbook.md`
- Release Mapping Record -> `rollback_runbook.md`
- Common Inspection Queries -> `rollback_runbook.md`
