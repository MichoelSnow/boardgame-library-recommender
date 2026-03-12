# Validation Scripts

## Workflow Entry Points

## `validate_dev_deploy.py`
- What it does:
  - Runs the full dev post-merge validation chain.
  - Writes validated SHA to `.tmp/validated_dev_sha.txt`.
- When to use:
  - After merge/deploy to `dev`.
- How to use:
```bash
poetry run python scripts/validate/validate_dev_deploy.py
```

## `validate_prod_release.py`
- What it does:
  - Runs full prod release validation using SHA validated in `dev`.
- When to use:
  - After prod promotion.
- How to use:
```bash
poetry run python scripts/validate/validate_prod_release.py
```

## Alert Wiring

## `validate_prod_alert_path.py`
- What it does:
  - Verifies workflow schedule/command wiring for prod alert checks.
  - Optional runtime dry-run execution.
- How to use:
```bash
poetry run python scripts/validate/validate_prod_alert_path.py --env prod --skip-runtime
poetry run python scripts/validate/validate_prod_alert_path.py --env prod
```

## Component Checks

## `validate_fly_release.py`
- Verifies `/api`, `/api/version`, expected SHA, and build timestamp.
```bash
poetry run python scripts/validate/validate_fly_release.py --env dev --expected-ref HEAD
```

## `validate_fly_health_checks.py`
- Verifies Fly health checks exist and are passing.
```bash
poetry run python scripts/validate/validate_fly_health_checks.py --env dev
```

## `validate_auth_flow.py`
- Verifies unauthorized rejection and optional positive smoke login.
```bash
poetry run python scripts/validate/validate_auth_flow.py --env dev
```

## `validate_recommendation_artifacts.py`
- Verifies embedding/mapping artifacts exist and timestamp pairs match.
```bash
poetry run python scripts/validate/validate_recommendation_artifacts.py --env dev
```

## `validate_recommendation_endpoint.py`
- Verifies recommendation endpoint returns non-empty results for a known-good game.
```bash
poetry run python scripts/validate/validate_recommendation_endpoint.py --env dev --game-id 224517
```

## `validate_performance_gate.py`
- Verifies latency thresholds for `/api`, `/api/version`, and recommendations.
```bash
poetry run python scripts/validate/validate_performance_gate.py --env dev --game-id 224517
```

## Notebook Hygiene Checks

## `validate_notebook_outputs.py`
- Verifies notebooks have no outputs/execution counts and no unexpected non-notebook artifacts.
```bash
python scripts/validate/validate_notebook_outputs.py
```

## `validate_notebook_secrets.py`
- Scans notebook source and outputs for common credential/secret leak patterns.
```bash
python scripts/validate/validate_notebook_secrets.py
```

## Dependency Audit Checks

## `validate_frontend_audit.py`
- Runs `npm audit --omit=dev --json` and enforces baseline allowlist policy.
```bash
poetry run python scripts/validate/validate_frontend_audit.py
```

## `validate_python_audit.py`
- Runs `pip-audit --format json` and enforces baseline allowlist policy.
```bash
poetry run python scripts/validate/validate_python_audit.py
```
