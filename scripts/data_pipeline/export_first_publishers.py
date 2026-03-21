#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import logging
from pathlib import Path

import duckdb


logger = logging.getLogger(__name__)


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def find_source_table(connection: duckdb.DuckDBPyConnection) -> str:
    tables = [row[0] for row in connection.execute("SHOW TABLES").fetchall()]
    for table_name in tables:
        columns = {
            row[0].lower()
            for row in connection.execute(f"DESCRIBE {table_name}").fetchall()
        }
        if "id" in columns and "payload_json" in columns:
            return table_name
    raise RuntimeError(
        "Could not find a table containing both 'id' and 'payload_json'."
    )


def extract_first_publisher(payload_json: str | None) -> str:
    if not payload_json:
        return ""

    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return ""

    publisher_obj = payload.get("boardgamepublisher")
    if not isinstance(publisher_obj, dict) or not publisher_obj:
        return ""

    first_value = next(iter(publisher_obj.values()), "")
    return str(first_value) if first_value is not None else ""


def export_publishers(
    duckdb_path: Path, output_csv: Path, table_name: str | None
) -> int:
    logger.info("Reading from DuckDB: %s", duckdb_path)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(str(duckdb_path), read_only=True) as connection:
        source_table = table_name or find_source_table(connection)
        logger.info("Using table: %s", source_table)
        rows = connection.execute(
            f"SELECT id, payload_json FROM {source_table} ORDER BY id"
        ).fetchall()

    logger.info("Loaded %s rows", len(rows))
    with output_csv.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["id", "publisher"])
        for row_id, payload_json in rows:
            writer.writerow([row_id, extract_first_publisher(payload_json)])

    logger.info("Wrote CSV: %s", output_csv)
    return len(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract id and the first boardgamepublisher value from payload_json in a DuckDB file."
        )
    )
    parser.add_argument(
        "--duckdb",
        default="data/ingest/game_data/boardgame_data_1773952692.duckdb",
        help="Path to source DuckDB file.",
    )
    parser.add_argument(
        "--output",
        default="data/ingest/game_data/first_publishers.csv",
        help="Path to output CSV file.",
    )
    parser.add_argument(
        "--table",
        default=None,
        help="Optional explicit source table name. If omitted, auto-detected.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging(args.verbose)
    export_publishers(
        duckdb_path=Path(args.duckdb),
        output_csv=Path(args.output),
        table_name=args.table,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
