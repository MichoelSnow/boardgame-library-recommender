"""Shared DuckDB storage helpers for boardgame data payloads."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd


def initialize_game_data_store(connection: duckdb.DuckDBPyConnection) -> None:
    """Create the shared boardgame data table when it does not exist."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS boardgame_data (
            id BIGINT PRIMARY KEY,
            payload_json TEXT
        );
        """
    )


def upsert_game_data_batch(
    connection: duckdb.DuckDBPyConnection,
    game_dicts: list[dict[str, object]],
) -> None:
    """Upsert a batch of JSON-backed boardgame records."""
    if not game_dicts:
        return
    rows = [
        {"id": int(game_dict["id"]), "payload_json": json.dumps(game_dict)}
        for game_dict in game_dicts
    ]
    df_rows = pd.DataFrame(rows)
    connection.register("game_data_tmp", df_rows)
    try:
        connection.execute(
            """
            INSERT OR REPLACE INTO boardgame_data (id, payload_json)
            SELECT id, payload_json
            FROM game_data_tmp;
            """
        )
    finally:
        connection.unregister("game_data_tmp")


def load_game_data_from_connection(
    connection: duckdb.DuckDBPyConnection,
) -> pd.DataFrame:
    """Load JSON-backed boardgame data from an open DuckDB connection."""
    payload_rows = connection.execute(
        "SELECT payload_json FROM boardgame_data ORDER BY id"
    ).fetchall()
    if not payload_rows:
        return pd.DataFrame()
    records = [json.loads(row[0]) for row in payload_rows]
    return pd.DataFrame(records)


def load_game_data_from_duckdb(duckdb_path: Path) -> pd.DataFrame:
    """Load JSON-backed boardgame data from a DuckDB file."""
    connection = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        return load_game_data_from_connection(connection)
    finally:
        connection.close()


def replace_game_data_in_duckdb(
    boardgame_data: pd.DataFrame,
    save_path: Path,
) -> None:
    """Replace the boardgame data snapshot in a DuckDB file."""
    connection = duckdb.connect(str(save_path))
    try:
        initialize_game_data_store(connection)
        rows = [
            {"id": int(record["id"]), "payload_json": json.dumps(record)}
            for record in boardgame_data.to_dict(orient="records")
        ]
        df_rows = pd.DataFrame(rows)
        connection.register("game_data_tmp", df_rows)
        try:
            connection.execute("DELETE FROM boardgame_data;")
            connection.execute(
                """
                INSERT INTO boardgame_data (id, payload_json)
                SELECT id, payload_json
                FROM game_data_tmp;
                """
            )
        finally:
            connection.unregister("game_data_tmp")
    finally:
        connection.close()
