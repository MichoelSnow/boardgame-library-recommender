#!/usr/bin/env python
import argparse
import logging
import sys
from pathlib import Path
from typing import Iterable, Iterator, Sequence

from sqlalchemy import MetaData, create_engine, func, select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.sql.schema import Table


backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.db_config import get_database_url, get_default_sqlite_path  # noqa: E402
from app.logging_utils import build_log_handlers  # noqa: E402
from app.models import Base  # noqa: E402


logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 1000


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=build_log_handlers("sqlite_to_postgres_migration.log"),
    )


def build_default_sqlite_url() -> str:
    return f"sqlite:///{get_default_sqlite_path()}"


def get_table_copy_order() -> list[str]:
    return [table.name for table in Base.metadata.sorted_tables]


def iter_batches(rows: Sequence[dict], batch_size: int) -> Iterator[list[dict]]:
    for start in range(0, len(rows), batch_size):
        yield list(rows[start : start + batch_size])


def reflect_tables(engine: Engine) -> dict[str, Table]:
    metadata = MetaData()
    metadata.reflect(bind=engine)
    return metadata.tables


def get_table_row_count(connection: Connection, table: Table) -> int:
    statement = select(func.count()).select_from(table)
    return int(connection.execute(statement).scalar_one())


def fetch_source_rows(connection: Connection, table: Table) -> list[dict]:
    result = connection.execute(select(table))
    return [dict(row._mapping) for row in result]


def get_valid_game_ids(source_connection: Connection, games_table: Table) -> set[int]:
    result = source_connection.execute(select(games_table.c.id))
    return {int(row[0]) for row in result}


def normalize_row_for_target(
    table_name: str,
    row: dict,
    valid_game_ids: set[int] | None = None,
) -> dict:
    normalized_row = dict(row)

    if table_name == "pax_games":
        bgg_id = normalized_row.get("bgg_id")
        if bgg_id == 0:
            normalized_row["bgg_id"] = None
        elif (
            bgg_id is not None
            and valid_game_ids is not None
            and int(bgg_id) not in valid_game_ids
        ):
            normalized_row["bgg_id"] = None

    return normalized_row


def ensure_target_tables_exist(
    table_order: Iterable[str],
    source_tables: dict[str, Table],
    target_tables: dict[str, Table],
) -> None:
    missing_source = [name for name in table_order if name not in source_tables]
    if missing_source:
        raise RuntimeError(
            f"Source database is missing expected tables: {', '.join(missing_source)}"
        )

    missing_target = [name for name in table_order if name not in target_tables]
    if missing_target:
        raise RuntimeError(
            f"Target database is missing expected tables: {', '.join(missing_target)}"
        )


def ensure_target_is_empty(
    table_order: Iterable[str],
    target_connection: Connection,
    target_tables: dict[str, Table],
) -> None:
    non_empty_tables: list[str] = []
    for table_name in table_order:
        if get_table_row_count(target_connection, target_tables[table_name]) > 0:
            non_empty_tables.append(table_name)

    if non_empty_tables:
        raise RuntimeError(
            "Target database is not empty. Refusing to migrate into populated tables: "
            + ", ".join(non_empty_tables)
        )


def migrate_table(
    table_name: str,
    source_connection: Connection,
    target_connection: Connection,
    source_table: Table,
    target_table: Table,
    batch_size: int,
    valid_game_ids: set[int] | None = None,
) -> tuple[int, int]:
    rows = [
        normalize_row_for_target(table_name, row, valid_game_ids=valid_game_ids)
        for row in fetch_source_rows(source_connection, source_table)
    ]
    source_count = len(rows)

    if rows:
        for batch in iter_batches(rows, batch_size):
            target_connection.execute(target_table.insert(), batch)

    target_count = get_table_row_count(target_connection, target_table)
    if source_count != target_count:
        raise RuntimeError(
            f"Row-count mismatch for {table_name}: source={source_count}, target={target_count}"
        )

    logger.info(
        "Migrated table %s successfully (rows=%s).",
        table_name,
        source_count,
    )
    return source_count, target_count


def migrate_sqlite_to_postgres(
    source_database_url: str,
    target_database_url: str,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> None:
    if not source_database_url.startswith("sqlite:///"):
        raise RuntimeError("Source database must be a SQLite URL.")

    if target_database_url.startswith("sqlite:///"):
        raise RuntimeError("Target database must be a non-SQLite URL.")

    source_engine = create_engine(source_database_url)
    target_engine = create_engine(target_database_url)

    table_order = get_table_copy_order()
    source_tables = reflect_tables(source_engine)
    target_tables = reflect_tables(target_engine)
    ensure_target_tables_exist(table_order, source_tables, target_tables)

    with source_engine.connect() as source_connection, target_engine.begin() as target_connection:
        ensure_target_is_empty(table_order, target_connection, target_tables)
        valid_game_ids = get_valid_game_ids(source_connection, source_tables["games"])

        for table_name in table_order:
            migrate_table(
                table_name=table_name,
                source_connection=source_connection,
                target_connection=target_connection,
                source_table=source_tables[table_name],
                target_table=target_tables[table_name],
                batch_size=batch_size,
                valid_game_ids=valid_game_ids,
            )

    logger.info("SQLite to Postgres migration completed successfully.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy application data from SQLite into a Postgres database."
    )
    parser.add_argument(
        "--source-url",
        default=build_default_sqlite_url(),
        help="Source SQLite database URL. Defaults to the local app SQLite database.",
    )
    parser.add_argument(
        "--target-url",
        default=None,
        help="Target Postgres database URL. Defaults to DATABASE_URL from the environment.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Number of rows to insert per batch.",
    )
    return parser.parse_args()


def main() -> int:
    configure_logging()
    args = parse_args()

    target_url = args.target_url or get_database_url()
    if not target_url:
        logger.error("Target database URL is required.")
        return 1

    try:
        migrate_sqlite_to_postgres(
            source_database_url=args.source_url,
            target_database_url=target_url,
            batch_size=args.batch_size,
        )
    except Exception as exc:
        logger.error("SQLite to Postgres migration failed: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
