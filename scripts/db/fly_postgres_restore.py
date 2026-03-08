import argparse
import logging
import subprocess
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = CURRENT_DIR.parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

try:
    from fly_postgres_common import build_ssh_console_command
except ModuleNotFoundError:
    from scripts.fly_postgres_common import build_ssh_console_command


LOGGER = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def build_drop_database_command(environment: str, postgres_user: str, restore_db: str) -> list[str]:
    remote_command = (
        f'psql -U {postgres_user} -d postgres -c "DROP DATABASE IF EXISTS {restore_db} WITH (FORCE);"'
    )
    return build_ssh_console_command(environment, remote_command)


def build_create_database_command(environment: str, postgres_user: str, restore_db: str) -> list[str]:
    remote_command = f'psql -U {postgres_user} -d postgres -c "CREATE DATABASE {restore_db};"'
    return build_ssh_console_command(environment, remote_command)


def build_restore_command(environment: str, postgres_user: str, restore_db: str) -> list[str]:
    remote_command = f"psql -U {postgres_user} -d {restore_db}"
    return build_ssh_console_command(environment, remote_command)


def build_verify_command(environment: str, postgres_user: str, restore_db: str) -> list[str]:
    remote_command = (
        "psql "
        f"-U {postgres_user} -d {restore_db} "
        "-tAc \"SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';\""
    )
    return build_ssh_console_command(environment, remote_command)


def run_restore(input_path: Path, restore_command: list[str]) -> None:
    with input_path.open("rb") as input_file:
        subprocess.run(restore_command, check=True, stdin=input_file)


def verify_restore(verify_command: list[str]) -> None:
    result = subprocess.run(
        verify_command,
        check=True,
        capture_output=True,
        text=True,
    )
    table_count = int(result.stdout.strip() or "0")
    if table_count <= 0:
        raise RuntimeError("Restore verification failed: no public tables found.")
    LOGGER.info("Restore verification succeeded (%s public tables).", table_count)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Restore a Fly Postgres SQL dump into a disposable test database."
    )
    parser.add_argument(
        "--env",
        required=True,
        choices=["dev", "prod"],
        help="Target Fly database environment.",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to the local SQL dump file created by fly_postgres_backup.py.",
    )
    parser.add_argument(
        "--postgres-user",
        default="pax_tt_app",
        help="Database user for restore operations (default: pax_tt_app).",
    )
    parser.add_argument(
        "--restore-db",
        default="pax_tt_recommender_restore_test",
        help="Disposable database name to recreate and restore into.",
    )
    return parser.parse_args()


def main() -> int:
    configure_logging()
    args = parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Restore input file does not exist: {input_path}")
    if input_path.stat().st_size == 0:
        raise RuntimeError(f"Restore input file is empty: {input_path}")

    LOGGER.info("Recreating disposable restore database: %s", args.restore_db)
    subprocess.run(
        build_drop_database_command(args.env, args.postgres_user, args.restore_db),
        check=True,
    )
    subprocess.run(
        build_create_database_command(args.env, args.postgres_user, args.restore_db),
        check=True,
    )

    LOGGER.info("Restoring %s into %s", input_path, args.restore_db)
    run_restore(input_path, build_restore_command(args.env, args.postgres_user, args.restore_db))
    verify_restore(build_verify_command(args.env, args.postgres_user, args.restore_db))
    LOGGER.info("Restore completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
