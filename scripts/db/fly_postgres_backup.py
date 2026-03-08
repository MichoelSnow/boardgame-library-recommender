import argparse
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = CURRENT_DIR.parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

try:
    from fly_postgres_common import DB_APP_BY_ENV, build_ssh_console_command
except ModuleNotFoundError:
    from scripts.fly_postgres_common import DB_APP_BY_ENV, build_ssh_console_command

LOGGER = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def build_default_output_path(environment: str, output_dir: str = "/tmp") -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(output_dir) / f"pax-tt-{environment}-postgres-backup-{timestamp}.sql"


def build_pg_dump_command(environment: str, postgres_user: str, postgres_db: str) -> list[str]:
    remote_command = (
        f"pg_dump -U {postgres_user} -d {postgres_db} "
        "--clean --if-exists --no-owner --no-privileges"
    )
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a logical SQL backup from a self-managed Fly Postgres app."
    )
    parser.add_argument(
        "--env",
        required=True,
        choices=sorted(DB_APP_BY_ENV.keys()),
        help="Target Fly database environment.",
    )
    parser.add_argument(
        "--postgres-user",
        default="pax_tt_app",
        help="Database user for pg_dump (default: pax_tt_app).",
    )
    parser.add_argument(
        "--postgres-db",
        default="pax_tt_recommender",
        help="Database name for pg_dump (default: pax_tt_recommender).",
    )
    parser.add_argument(
        "--output",
        help="Local output file path. Defaults to a timestamped file under /tmp.",
    )
    return parser.parse_args()


def main() -> int:
    configure_logging()
    args = parse_args()
    output_path = Path(args.output) if args.output else build_default_output_path(args.env)
    command = build_pg_dump_command(args.env, args.postgres_user, args.postgres_db)
    write_backup(command, output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
