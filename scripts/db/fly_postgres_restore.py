import argparse
import logging
import os
import shlex
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
REPO_ROOT = CURRENT_DIR.parent.parent


def load_repo_env_if_present() -> None:
    """Load repo-root .env values into process env without overriding existing vars."""
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def build_drop_database_command(
    environment: str, postgres_user: str, restore_db: str
) -> list[str]:
    remote_command = f'psql -U {postgres_user} -d postgres -c "DROP DATABASE IF EXISTS {restore_db} WITH (FORCE);"'
    return build_ssh_console_command(environment, remote_command)


def build_create_database_command(
    environment: str, postgres_user: str, restore_db: str
) -> list[str]:
    remote_command = (
        f'psql -U {postgres_user} -d postgres -c "CREATE DATABASE {restore_db};"'
    )
    return build_ssh_console_command(environment, remote_command)


def build_restore_command(
    environment: str, postgres_user: str, restore_db: str
) -> list[str]:
    remote_command = f"psql -U {postgres_user} -d {restore_db}"
    return build_ssh_console_command(environment, remote_command)


def build_restore_from_remote_file_command(
    environment: str, postgres_user: str, restore_db: str, remote_input: str
) -> list[str]:
    quoted_user = shlex.quote(postgres_user)
    quoted_db = shlex.quote(restore_db)
    quoted_remote_input = shlex.quote(remote_input)
    remote_command = "sh -lc " + shlex.quote(
        f"test -s {quoted_remote_input} && "
        f"psql -U {quoted_user} -d {quoted_db} -v ON_ERROR_STOP=1 -f {quoted_remote_input}"
    )
    return build_ssh_console_command(environment, remote_command)


def build_delete_remote_file_command(environment: str, remote_input: str) -> list[str]:
    quoted_remote_input = shlex.quote(remote_input)
    remote_command = "sh -lc " + shlex.quote(f"rm -f {quoted_remote_input}")
    return build_ssh_console_command(environment, remote_command)


def build_verify_command(
    environment: str, postgres_user: str, restore_db: str
) -> list[str]:
    remote_command = (
        "psql "
        f"-U {postgres_user} -d {restore_db} "
        "-tAc \"SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';\""
    )
    return build_ssh_console_command(environment, remote_command)


def run_restore(input_path: Path, restore_command: list[str]) -> None:
    with input_path.open("rb") as input_file:
        subprocess.run(restore_command, check=True, stdin=input_file)


def run_restore_from_remote_input(
    environment: str, postgres_user: str, restore_db: str, remote_input: str
) -> None:
    subprocess.run(
        build_restore_from_remote_file_command(
            environment=environment,
            postgres_user=postgres_user,
            restore_db=restore_db,
            remote_input=remote_input,
        ),
        check=True,
    )


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
    default_user = os.getenv("POSTGRES_USER", "postgres")
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
        help="Path to the local SQL dump file created by fly_postgres_backup.py.",
    )
    parser.add_argument(
        "--remote-input",
        help=(
            "Path to SQL dump file that already exists on the remote Fly DB machine. "
            "Mutually exclusive with --input."
        ),
    )
    parser.add_argument(
        "--postgres-user",
        default=default_user,
        help=f"Database user for restore operations (default: {default_user}).",
    )
    parser.add_argument(
        "--restore-db",
        default="bg_lib_recommender_restore_test",
        help="Disposable database name to recreate and restore into.",
    )
    parser.add_argument(
        "--delete-remote-after-restore",
        action="store_true",
        help=(
            "Delete --remote-input file after a successful restore. "
            "Only valid with --remote-input."
        ),
    )
    args = parser.parse_args()
    if bool(args.input) == bool(args.remote_input):
        parser.error("Provide exactly one of --input or --remote-input.")
    if args.delete_remote_after_restore and not args.remote_input:
        parser.error("--delete-remote-after-restore requires --remote-input.")
    return args


def main() -> int:
    load_repo_env_if_present()
    configure_logging()
    args = parse_args()

    LOGGER.info("Recreating disposable restore database: %s", args.restore_db)
    subprocess.run(
        build_drop_database_command(args.env, args.postgres_user, args.restore_db),
        check=True,
    )
    subprocess.run(
        build_create_database_command(args.env, args.postgres_user, args.restore_db),
        check=True,
    )

    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            raise FileNotFoundError(f"Restore input file does not exist: {input_path}")
        if input_path.stat().st_size == 0:
            raise RuntimeError(f"Restore input file is empty: {input_path}")
        LOGGER.info("Restoring local file %s into %s", input_path, args.restore_db)
        run_restore(
            input_path,
            build_restore_command(args.env, args.postgres_user, args.restore_db),
        )
    else:
        LOGGER.info(
            "Restoring remote file %s into %s", args.remote_input, args.restore_db
        )
        run_restore_from_remote_input(
            environment=args.env,
            postgres_user=args.postgres_user,
            restore_db=args.restore_db,
            remote_input=args.remote_input,
        )

    verify_restore(build_verify_command(args.env, args.postgres_user, args.restore_db))
    if args.remote_input and args.delete_remote_after_restore:
        LOGGER.info("Deleting remote backup file: %s", args.remote_input)
        subprocess.run(
            build_delete_remote_file_command(args.env, args.remote_input), check=True
        )
    LOGGER.info("Restore completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
