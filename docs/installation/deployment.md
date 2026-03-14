# Deployment

First-time setup and deployment guide from a fresh clone.

This guide covers three supported runtime targets:

1. Local SQLite
2. Local Postgres
3. Fly.io Postgres (from scratch)

This guide intentionally gets you to an **empty but working app**. Data ingest/import is handled separately.

## 1. Prerequisites

Install required tools:

- `git`
- `python` 3.10
- `poetry`
- `node` + `npm`
- `flyctl` (for Fly.io mode)
- `psql` client (recommended for DB checks)

## 2. Clone and Install

```bash
git clone <your-fork-or-repo-url>
cd <repo-directory>

poetry install
cd frontend && npm ci
cd ..
```

## 3. Generate Strong Secrets

Use the repo script to generate and write secrets safely and cleanly:

```bash
bash scripts/deploy/generate_env_secrets.sh .env
```

Optional: choose your own Fly app-name prefix (recommended):

```bash
bash scripts/deploy/generate_env_secrets.sh .env myprefix
```

If no prefix is provided, the script defaults to `${USER}-bg`.

Load env values into your current shell when running commands from this guide:

```bash
set -a
source .env
set +a
```

What it does:

- creates the target env file if missing (here: `.env`)
- enforces `chmod 600` on the target env file
- replaces managed keys atomically (no duplicate stale entries)
- writes consistent defaults for local/Fly deployment keys
- updates Fly app names in:
  - `fly.dev.toml`
  - `fly.toml`
  - `fly.db.dev.toml`
  - `fly.db.prod.toml`

Security note:

- keep `.env` out of git and do not share it.

## 4. Mode A: Local SQLite

Uses generated `.env` values (`SECRET_KEY`, `DATABASE_PATH`).

### 4.1 Run migrations and start backend

```bash
set -a
source .env
set +a

unset DATABASE_URL
poetry run alembic upgrade head
poetry run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4.2 Verify

```bash
poetry run python -c "from backend.app.db_config import get_database_url; print(get_database_url())"
curl -sS http://localhost:8000/api
```

Expected:

- DB URL starts with `sqlite:///`
- `/api` responds with JSON

## 5. Mode B: Local Postgres

Uses generated `.env` values (`POSTGRES_*_LOCAL`, `POSTGRES_USER`, `POSTGRES_DB`, `SECRET_KEY`).

### 5.1 Start a local Postgres (Docker quick path)

```bash
docker run --name boardgame-pg-local \
  -e POSTGRES_USER="${POSTGRES_USER}" \
  -e POSTGRES_PASSWORD="${POSTGRES_PASSWORD_LOCAL}" \
  -e POSTGRES_DB="${POSTGRES_DB}" \
  -p "${POSTGRES_PORT_LOCAL}:5432" \
  -d postgres:18.3
```

### 5.2 Set `DATABASE_URL`, run migrations, start backend

```bash
set -a
source .env
set +a

export DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD_LOCAL}@${POSTGRES_HOST_LOCAL}:${POSTGRES_PORT_LOCAL}/${POSTGRES_DB}"
poetry run alembic upgrade head
poetry run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5.3 Verify

```bash
poetry run python -c "from backend.app.db_config import get_database_url; print(get_database_url())"
psql "${DATABASE_URL}" -c "SELECT 1;"
curl -sS http://localhost:8000/api
```

Expected:

- DB URL starts with `postgresql://`
- SQL `SELECT 1` succeeds
- `/api` responds

## 6. Mode C: Fly.io Postgres (From Scratch)

This section creates new Fly apps and volumes from zero.

`FLY_*_NAME_*` values must be globally unique across Fly.io. The generator script sets defaults based on your local username, but you can override with:

```bash
APP_PREFIX=<your-unique-prefix> bash scripts/deploy/generate_env_secrets.sh .env
```

### 6.1 Fly auth

```bash
fly auth login
fly orgs list
```

### 6.2 Create Fly apps

```bash
set -a && source .env && set +a

fly apps create "${FLY_DB_APP_NAME_DEV}"
fly apps create "${FLY_DB_APP_NAME_PROD}"
fly apps create "${FLY_APP_NAME_DEV}"
fly apps create "${FLY_APP_NAME_PROD}"
```

The secret-generation script already rewrites `app = '...'` in `fly*.toml` files to match your chosen `FLY_*` names.

### 6.3 Create volumes (4GB)

```bash
fly volumes create pg_data_dev --size 4 --region "${FLY_REGION}" --app "${FLY_DB_APP_NAME_DEV}"
fly volumes create pg_data_prod --size 4 --region "${FLY_REGION}" --app "${FLY_DB_APP_NAME_PROD}"
fly volumes create boardgames_data_dev --size 4 --region "${FLY_REGION}" --app "${FLY_APP_NAME_DEV}"
fly volumes create boardgames_data --size 4 --region "${FLY_REGION}" --app "${FLY_APP_NAME_PROD}"
```

### 6.4 Set DB app secrets

```bash
fly secrets set -a "${FLY_DB_APP_NAME_DEV}" POSTGRES_USER=postgres POSTGRES_PASSWORD="${POSTGRES_PASSWORD_DEV}" POSTGRES_DB="${POSTGRES_DB}"
fly secrets set -a "${FLY_DB_APP_NAME_PROD}" POSTGRES_USER=postgres POSTGRES_PASSWORD="${POSTGRES_PASSWORD_PROD}" POSTGRES_DB="${POSTGRES_DB}"
```

### 6.5 Deploy DB apps

```bash
fly deploy -c fly.db.dev.toml -a "${FLY_DB_APP_NAME_DEV}"
fly deploy -c fly.db.prod.toml -a "${FLY_DB_APP_NAME_PROD}"
```

Answer `No` to the question "Would you like to allocate dedicated ipv4 and ipv6 addresses now?" for both deployments.

### 6.6 Verify DB apps

```bash
fly status -a "${FLY_DB_APP_NAME_DEV}"
fly status -a "${FLY_DB_APP_NAME_PROD}"

fly ssh console -a "${FLY_DB_APP_NAME_DEV}" -C "psql \"postgresql://postgres:${POSTGRES_PASSWORD_DEV}@127.0.0.1:5432/${POSTGRES_DB}\" -c \"SELECT 1;\""
fly ssh console -a "${FLY_DB_APP_NAME_PROD}" -C "psql \"postgresql://postgres:${POSTGRES_PASSWORD_PROD}@127.0.0.1:5432/${POSTGRES_DB}\" -c \"SELECT 1;\""
```

### 6.7 Ensure Flycast is provisioned for DB apps

App-to-DB autostart via `*.flycast` requires each DB app to have a private Flycast IP.

```bash
fly ips list -a "${FLY_DB_APP_NAME_DEV}"
fly ips list -a "${FLY_DB_APP_NAME_PROD}"
```

If either app does not show a private Flycast IP, allocate one:

```bash
fly ips allocate-v6 --private -a "${FLY_DB_APP_NAME_DEV}"
fly ips allocate-v6 --private -a "${FLY_DB_APP_NAME_PROD}"
```

### 6.8 Set app secrets

```bash
fly secrets set -a "${FLY_APP_NAME_DEV}" DATABASE_URL="postgresql://postgres:${POSTGRES_PASSWORD_DEV}@${FLY_DB_APP_NAME_DEV}.flycast:5432/${POSTGRES_DB}" SECRET_KEY="${SECRET_KEY_DEV}" CONVENTION_KIOSK_KEY="${CONVENTION_KIOSK_KEY_DEV}" CORS_ALLOWED_ORIGINS="https://${FLY_APP_NAME_DEV}.fly.dev,https://${FLY_APP_NAME_PROD}.fly.dev"
fly secrets set -a "${FLY_APP_NAME_PROD}" DATABASE_URL="postgresql://postgres:${POSTGRES_PASSWORD_PROD}@${FLY_DB_APP_NAME_PROD}.flycast:5432/${POSTGRES_DB}" SECRET_KEY="${SECRET_KEY_PROD}" CONVENTION_KIOSK_KEY="${CONVENTION_KIOSK_KEY_PROD}" CORS_ALLOWED_ORIGINS="https://${FLY_APP_NAME_PROD}.fly.dev,https://${FLY_APP_NAME_DEV}.fly.dev"
```

Use `.flycast` hostnames for Fly Postgres app URLs so DB autostart works reliably when app machines wake from stopped state.

### 6.9 Deploy app services

```bash
fly deploy -c fly.dev.toml -a "${FLY_APP_NAME_DEV}"
fly deploy -c fly.toml -a "${FLY_APP_NAME_PROD}"
```

### 6.10 Verify app can resolve DB Flycast hostnames

This precheck prevents baseline/stamp failures.

```bash
fly ssh console -a "${FLY_APP_NAME_DEV}" -C "python -c \"import socket; print(socket.getaddrinfo('${FLY_DB_APP_NAME_DEV}.flycast', 5432))\""
fly ssh console -a "${FLY_APP_NAME_PROD}" -C "python -c \"import socket; print(socket.getaddrinfo('${FLY_DB_APP_NAME_PROD}.flycast', 5432))\""
```

Expected success output:

- A non-empty Python list of address tuples.
- Typically includes `AddressFamily.AF_INET6` and an `fdaa:...` address with port `5432`.

Example:

```text
[(<AddressFamily.AF_INET6: 10>, <SocketKind.SOCK_STREAM: 1>, 6, '', ('fdaa:20:5e2e:0:1::6', 5432, 0, 0)), ...]
```

Failure output (do not proceed to 6.11):

- `socket.gaierror: [Errno -2] Name or service not known`
- `socket.gaierror: [Errno -5] No address associated with hostname`

If lookup fails, re-check step 6.7 and redeploy the corresponding DB app:

```bash
fly deploy -c fly.db.dev.toml -a "${FLY_DB_APP_NAME_DEV}"
fly deploy -c fly.db.prod.toml -a "${FLY_DB_APP_NAME_PROD}"
```

### 6.11 Choose One DB Initialization Path (Mutually Exclusive)

Pick exactly one:

- **6.11A Baseline bootstrap** for fresh installs/resets (new DB, or intentional reset).
- **6.11B Alembic upgrade** for in-place upgrades of an existing DB with data.

Do not run both in sequence for the same environment.

### 6.11A Initialize DB Schema Baseline (Fresh Fly Install)

```bash
poetry run python scripts/db/transform_canonical_schema.py --input .tmp/canonical_prod_schema.sql --output .tmp/canonical_repo_schema.sql
poetry run python scripts/db/bootstrap_fly_postgres_baseline.py --env dev --schema-file .tmp/canonical_repo_schema.sql --reset-db
poetry run python scripts/db/bootstrap_fly_postgres_baseline.py --env prod --schema-file .tmp/canonical_repo_schema.sql --reset-db
```

This path applies the canonical schema and then stamps Alembic to `head` without replaying legacy revisions.
The bootstrap script will auto-start the app machine temporarily for the `alembic stamp head` step.

Migration workflows (copying data/artifacts between old and new machines) are documented in `docs/installation/migration.md`.

### 6.11B Existing DB Upgrade Path (Only for Real Upgrade Scenarios)

Use this only when upgrading an already-running database in place:

```bash
fly ssh console -a "${FLY_APP_NAME_DEV}" -C "sh -lc 'cd /app/backend && poetry run alembic upgrade head'"
fly ssh console -a "${FLY_APP_NAME_PROD}" -C "sh -lc 'cd /app/backend && poetry run alembic upgrade head'"
```

Legacy migration chain is retained for compatibility/history only and is marked for future archival in `backend/alembic/versions/README.md`. For fresh installs, use step 6.11A baseline bootstrap instead.

### 6.12 Verify app services

```bash
fly status -a "${FLY_APP_NAME_DEV}"
fly status -a "${FLY_APP_NAME_PROD}"
fly status -a "${FLY_DB_APP_NAME_DEV}"
fly status -a "${FLY_DB_APP_NAME_PROD}"

fly ssh console -a "${FLY_APP_NAME_DEV}" -C "python -c \"from backend.app.db_config import get_database_url; print(get_database_url())\""
fly ssh console -a "${FLY_APP_NAME_PROD}" -C "python -c \"from backend.app.db_config import get_database_url; print(get_database_url())\""

curl -sS "https://${FLY_APP_NAME_DEV}.fly.dev/api"
curl -sS "https://${FLY_APP_NAME_PROD}.fly.dev/api"
```

Expected:

- Both app checks pass
- DB URL points to `${FLY_DB_APP_NAME_*}.flycast/${POSTGRES_DB}`
- `/api` responds on both
- DB apps can be set to `auto_stop_machines = "stop"` and `min_machines_running = 0`; app traffic through Flycast will auto-start DB machines

## 7. Optional: Create First Admin User

Local:

```bash
printf '%s' '<strong-password>' | poetry run python backend/app/main.py --username <admin-username> --password-stdin --admin
```

Fly dev:

```bash
fly ssh console -a "${FLY_APP_NAME_DEV}" -C "sh -lc \"printf '%s' '<strong-password>' | python backend/app/main.py --username <admin-username> --password-stdin --admin\""
```

## 8. Important Notes

- At this stage the app is expected to be mostly empty until pipeline data is imported.
- Recommendation endpoints will remain degraded until embeddings are generated and placed on runtime storage.
- Next doc (separate): data pipeline ingest/import workflow.
