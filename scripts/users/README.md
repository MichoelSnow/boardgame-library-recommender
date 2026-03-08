# User Utility Scripts

## `create_smoke_test_user.py`
- What it does:
  - Authenticates as admin and creates/refreshes the smoke-test user for validations.
- When to use:
  - Before auth validation scripts if smoke credentials are missing/outdated.
- How to use:
```bash
poetry run python scripts/users/create_smoke_test_user.py --env dev
poetry run python scripts/users/create_smoke_test_user.py --env prod
```
- Required environment variables:
  - `ADMIN_USERNAME`
  - `ADMIN_PASSWORD`
  - `SMOKE_TEST_USERNAME`
  - `SMOKE_TEST_PASSWORD_<ENV>` (`DEV` or `PROD`)
