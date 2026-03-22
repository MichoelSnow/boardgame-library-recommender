import argparse
import logging
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = CURRENT_DIR.parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

try:
    from fly_postgres_common import DB_APP_ENV_VAR_BY_ENV, build_ssh_console_command
except ModuleNotFoundError:
    from scripts.fly_postgres_common import (
        DB_APP_ENV_VAR_BY_ENV,
        build_ssh_console_command,
    )

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


def build_default_output_path(environment: str, output_dir: str = "/tmp") -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(output_dir) / f"bg-lib-{environment}-postgres-backup-{timestamp}.sql"


def build_pg_dump_command(
    environment: str, postgres_user: str, postgres_db: str
) -> list[str]:
    remote_command = (
        f"pg_dump -U {postgres_user} -d {postgres_db} "
        "--clean --if-exists --no-owner --no-privileges"
    )
    return build_ssh_console_command(environment, remote_command)


def build_remote_dump_command(
    environment: str, postgres_user: str, postgres_db: str, remote_output: str
) -> list[str]:
    remote_output_path = Path(remote_output)
    parent_dir = remote_output_path.parent if remote_output_path.parent else Path(".")
    quoted_parent = shlex.quote(str(parent_dir))
    quoted_output = shlex.quote(str(remote_output_path))
    quoted_user = shlex.quote(postgres_user)
    quoted_db = shlex.quote(postgres_db)
    dump_sql = (
        f"mkdir -p {quoted_parent} && "
        f"pg_dump -U {quoted_user} -d {quoted_db} "
        "--clean --if-exists --no-owner --no-privileges "
        f"> {quoted_output} && "
        f"test -s {quoted_output}"
    )
    remote_command = "sh -lc " + shlex.quote(dump_sql)
    return build_ssh_console_command(environment, remote_command)


def build_remote_file_size_command(environment: str, remote_output: str) -> list[str]:
    quoted_output = shlex.quote(remote_output)
    remote_command = "sh -lc " + shlex.quote(f"wc -c < {quoted_output}")
    return build_ssh_console_command(environment, remote_command)


def write_backup(command: list[str], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Writing backup to %s", output_path)
    LOGGER.info("Running command: %s", " ".join(command[:-1]) + " <remote pg_dump>")

    with output_path.open("wb") as output_file:
        subprocess.run(command, check=True, stdout=output_file)

    file_size = output_path.stat().st_size
    if file_size == 0:
        raise RuntimeError(f"Backup file is empty: {output_path}")

    LOGGER.info("Backup completed successfully (%s bytes).", file_size)


def write_backup_remote(
    environment: str, postgres_user: str, postgres_db: str, remote_output: str
) -> None:
    command = build_remote_dump_command(
        environment=environment,
        postgres_user=postgres_user,
        postgres_db=postgres_db,
        remote_output=remote_output,
    )
    LOGGER.info("Writing backup to remote path %s", remote_output)
    LOGGER.info("Running command: %s", " ".join(command))
    subprocess.run(command, check=True)

    size_command = build_remote_file_size_command(environment, remote_output)
    result = subprocess.run(
        size_command,
        check=True,
        capture_output=True,
        text=True,
    )
    file_size = int(result.stdout.strip() or "0")
    if file_size <= 0:
        raise RuntimeError(f"Remote backup file is empty: {remote_output}")
    LOGGER.info("Remote backup completed successfully (%s bytes).", file_size)


def parse_args() -> argparse.Namespace:
    default_user = os.getenv("POSTGRES_USER", "postgres")
    default_db = os.getenv("POSTGRES_DB", "boardgame_recommender")
    parser = argparse.ArgumentParser(
        description="Create a logical SQL backup from a self-managed Fly Postgres app."
    )
    parser.add_argument(
        "--env",
        required=True,
        choices=sorted(DB_APP_ENV_VAR_BY_ENV.keys()),
        help="Target Fly database environment.",
    )
    parser.add_argument(
        "--postgres-user",
        default=default_user,
        help=f"Database user for pg_dump (default: {default_user}).",
    )
    parser.add_argument(
        "--postgres-db",
        default=default_db,
        help=f"Database name for pg_dump (default: {default_db}).",
    )
    parser.add_argument(
        "--output",
        help="Local output file path. Defaults to a timestamped file under /tmp.",
    )
    parser.add_argument(
        "--remote-output",
        help=(
            "Remote output file path on the Fly DB machine (for example "
            "/var/lib/postgresql/backups/dev.sql). Mutually exclusive with --output."
        ),
    )
    args = parser.parse_args()
    if args.output and args.remote_output:
        parser.error("--output and --remote-output cannot be used together.")
    return args


def main() -> int:
    load_repo_env_if_present()
    configure_logging()
    args = parse_args()
    if args.remote_output:
        write_backup_remote(
            environment=args.env,
            postgres_user=args.postgres_user,
            postgres_db=args.postgres_db,
            remote_output=args.remote_output,
        )
    else:
        output_path = (
            Path(args.output) if args.output else build_default_output_path(args.env)
        )
        command = build_pg_dump_command(args.env, args.postgres_user, args.postgres_db)
        write_backup(command, output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
