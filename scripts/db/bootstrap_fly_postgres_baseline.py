#!/usr/bin/env python3

import argparse
import json
import logging
import os
import re
import subprocess
from pathlib import Path

LOGGER = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def require_env(var_name: str) -> str:
    value = os.getenv(var_name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {var_name}")
    return value


def validate_db_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(
            "postgres-db must match [A-Za-z_][A-Za-z0-9_]* for safe SQL usage."
        )
    return value


def build_db_url(postgres_user: str, password: str, database_name: str) -> str:
    return f"postgresql://{postgres_user}:{password}@127.0.0.1:5432/{database_name}"


def redact_sensitive_text(value: str) -> str:
    # Redact password in PostgreSQL URLs: postgresql://user:<password>@host/db
    return re.sub(
        r"(postgresql://[^:\s\"']+):[^@\s\"']+@",
        r"\1:***@",
        value,
    )


def format_command_for_log(command: list[str]) -> str:
    return " ".join(redact_sensitive_text(part) for part in command)


def run_command(command: list[str], *, stdin=None) -> None:
    LOGGER.info("Running: %s", format_command_for_log(command))
    subprocess.run(command, check=True, stdin=stdin)


def run_command_capture(command: list[str]) -> subprocess.CompletedProcess[str]:
    LOGGER.info("Running: %s", format_command_for_log(command))
    return subprocess.run(command, check=True, capture_output=True, text=True)


def ensure_app_machine_started(app_name: str) -> None:
    result = run_command_capture(["fly", "machines", "list", "-a", app_name, "--json"])
    machines = json.loads(result.stdout)
    if not machines:
        raise RuntimeError(
            f"No machines found for app {app_name}. Deploy the app before baseline stamping."
        )

    machine = machines[0]
    machine_id = machine.get("id")
    machine_state = (machine.get("state") or "").lower()
    if not machine_id:
        raise RuntimeError(f"Could not resolve machine id for app {app_name}.")

    if machine_state != "started":
        LOGGER.info(
            "Starting stopped machine %s for app %s (state=%s)",
            machine_id,
            app_name,
            machine_state or "unknown",
        )
        run_command(["fly", "machine", "start", machine_id, "-a", app_name])


def resolve_env_values(
    environment: str, postgres_db_override: str | None
) -> dict[str, str]:
    env_key = environment.upper()
    db_app_name = require_env(f"FLY_DB_APP_NAME_{env_key}")
    app_name = require_env(f"FLY_APP_NAME_{env_key}")
    password = require_env(f"POSTGRES_PASSWORD_{env_key}")
    postgres_db = postgres_db_override or require_env("POSTGRES_DB")
    postgres_db = validate_db_identifier(postgres_db)
    return {
        "db_app_name": db_app_name,
        "app_name": app_name,
        "password": password,
        "postgres_db": postgres_db,
    }


def reset_database(
    db_app_name: str, postgres_user: str, password: str, postgres_db: str
) -> None:
    admin_url = build_db_url(postgres_user, password, "postgres")
    remote_command = (
        f'psql "{admin_url}" -v ON_ERROR_STOP=1 '
        f'-c "DROP DATABASE IF EXISTS {postgres_db} WITH (FORCE);" '
        f'-c "CREATE DATABASE {postgres_db};"'
    )
    run_command(["fly", "ssh", "console", "-a", db_app_name, "-C", remote_command])


def apply_schema_file(
    schema_file: Path,
    db_app_name: str,
    postgres_user: str,
    password: str,
    postgres_db: str,
) -> None:
    db_url = build_db_url(postgres_user, password, postgres_db)
    remote_command = f'psql "{db_url}" -v ON_ERROR_STOP=1'
    with schema_file.open("rb") as sql_stream:
        run_command(
            ["fly", "ssh", "console", "-a", db_app_name, "-C", remote_command],
            stdin=sql_stream,
        )


def stamp_head(app_name: str) -> None:
    ensure_app_machine_started(app_name)
    remote_command = "sh -lc 'cd /app/backend && poetry run alembic stamp head'"
    run_command(["fly", "ssh", "console", "-a", app_name, "-C", remote_command])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap a Fly Postgres DB from canonical schema and stamp Alembic head."
    )
    parser.add_argument(
        "--env",
        required=True,
        choices=["dev", "prod"],
        help="Target environment.",
    )
    parser.add_argument(
        "--schema-file",
        default=".tmp/canonical_repo_schema.sql",
        help="Path to canonical schema SQL file.",
    )
    parser.add_argument(
        "--postgres-user",
        default="postgres",
        help="Postgres user used by self-managed Fly Postgres app.",
    )
    parser.add_argument(
        "--postgres-db",
        default=None,
        help="Postgres database name (defaults to POSTGRES_DB env var).",
    )
    parser.add_argument(
        "--reset-db",
        action="store_true",
        help="Drop and recreate target database before applying schema.",
    )
    return parser.parse_args()


def main() -> int:
    configure_logging()
    args = parse_args()
    schema_file = Path(args.schema_file)
    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_file}")
    if schema_file.stat().st_size == 0:
        raise RuntimeError(f"Schema file is empty: {schema_file}")

    env_values = resolve_env_values(args.env, args.postgres_db)
    db_app_name = env_values["db_app_name"]
    app_name = env_values["app_name"]
    password = env_values["password"]
    postgres_db = env_values["postgres_db"]

    if args.reset_db:
        LOGGER.info("Resetting database %s on %s", postgres_db, db_app_name)
        reset_database(db_app_name, args.postgres_user, password, postgres_db)

    LOGGER.info("Applying schema from %s to %s", schema_file, db_app_name)
    apply_schema_file(
        schema_file, db_app_name, args.postgres_user, password, postgres_db
    )

    LOGGER.info("Stamping Alembic head on app %s", app_name)
    stamp_head(app_name)
    LOGGER.info("Bootstrap complete for %s.", args.env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
