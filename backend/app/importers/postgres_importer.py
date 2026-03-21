from __future__ import annotations

import io

import pandas as pd
from sqlalchemy.engine import Engine

COPY_CHUNK_ROWS = 50000

GAME_SOURCE_TO_TARGET = {
    "id": "id",
    "name": "name",
    "description": "description",
    "thumbnail": "thumbnail",
    "image": "image",
    "minplayers": "min_players",
    "maxplayers": "max_players",
    "playingtime": "playing_time",
    "minplaytime": "min_playtime",
    "maxplaytime": "max_playtime",
    "minage": "min_age",
    "yearpublished": "year_published",
    "average": "average",
    "numratings": "num_ratings",
    "numcomments": "num_comments",
    "numweights": "num_weights",
    "averageweight": "average_weight",
    "stddev": "stddev",
    "median": "median",
    "owned": "owned",
    "trading": "trading",
    "wanting": "wanting",
    "wishing": "wishing",
    "bayesaverage": "bayes_average",
    "usersrated": "users_rated",
    "is_expansion": "is_expansion",
    "rank": "rank",
    "abstracts_rank": "abstracts_rank",
    "cgs_rank": "cgs_rank",
    "childrensgames_rank": "childrens_games_rank",
    "familygames_rank": "family_games_rank",
    "partygames_rank": "party_games_rank",
    "strategygames_rank": "strategy_games_rank",
    "thematic_rank": "thematic_rank",
    "wargames_rank": "wargames_rank",
}

RELATION_SPECS = [
    {
        "entity": "boardgamemechanic",
        "table": "mechanics",
        "columns": ["game_id", "boardgamemechanic_id", "boardgamemechanic_name"],
        "dedupe_on": ["game_id", "boardgamemechanic_name"],
        "dropna": ["game_id", "boardgamemechanic_name"],
    },
    {
        "entity": "boardgamecategory",
        "table": "categories",
        "columns": ["game_id", "boardgamecategory_id", "boardgamecategory_name"],
        "dedupe_on": ["game_id", "boardgamecategory_name"],
        "dropna": ["game_id", "boardgamecategory_name"],
    },
    {
        "entity": "boardgamedesigner",
        "table": "designers",
        "columns": ["game_id", "boardgamedesigner_id", "boardgamedesigner_name"],
        "dedupe_on": ["game_id", "boardgamedesigner_name"],
        "dropna": ["game_id", "boardgamedesigner_name"],
    },
    {
        "entity": "boardgameartist",
        "table": "artists",
        "columns": ["game_id", "boardgameartist_id", "boardgameartist_name"],
        "dedupe_on": ["game_id", "boardgameartist_name"],
        "dropna": ["game_id", "boardgameartist_name"],
    },
    {
        "entity": "boardgamepublisher",
        "table": "publishers",
        "columns": ["game_id", "boardgamepublisher_id", "boardgamepublisher_name"],
        "dedupe_on": ["game_id", "boardgamepublisher_name"],
        "dropna": ["game_id", "boardgamepublisher_name"],
    },
    {
        "entity": "boardgameintegration",
        "table": "integrations",
        "columns": ["game_id", "boardgameintegration_id", "boardgameintegration_name"],
        "dropna": ["game_id", "boardgameintegration_name"],
    },
    {
        "entity": "boardgameimplementation",
        "table": "implementations",
        "columns": [
            "game_id",
            "boardgameimplementation_id",
            "boardgameimplementation_name",
        ],
        "dropna": ["game_id", "boardgameimplementation_name"],
    },
    {
        "entity": "boardgamecompilation",
        "table": "compilations",
        "columns": ["game_id", "boardgamecompilation_id", "boardgamecompilation_name"],
        "dropna": ["game_id", "boardgamecompilation_name"],
    },
    {
        "entity": "boardgameexpansion",
        "table": "expansions",
        "columns": ["game_id", "boardgameexpansion_id", "boardgameexpansion_name"],
        "dropna": ["game_id", "boardgameexpansion_name"],
    },
    {
        "entity": "boardgamefamily",
        "table": "families",
        "columns": ["game_id", "boardgamefamily_id", "boardgamefamily_name"],
        "dropna": ["game_id", "boardgamefamily_name"],
    },
    {
        "entity": "suggested_num_players",
        "table": "suggested_players",
        "columns": [
            "game_id",
            "player_count",
            "best",
            "recommended",
            "not_recommended",
            "game_total_votes",
            "player_count_total_votes",
            "recommendation_level",
        ],
        "rename": {"total_votes": "player_count_total_votes"},
        "dropna": ["game_id", "player_count"],
    },
    {
        "entity": "language_dependence",
        "table": "language_dependence",
        "columns": [
            "game_id",
            "level_1",
            "level_2",
            "level_3",
            "level_4",
            "level_5",
            "total_votes",
            "language_dependency",
        ],
        "rename": {
            "id": "game_id",
            "1": "level_1",
            "2": "level_2",
            "3": "level_3",
            "4": "level_4",
            "5": "level_5",
        },
        "dropna": ["game_id"],
    },
    {
        "entity": "versions",
        "table": "versions",
        "columns": [
            "game_id",
            "version_id",
            "width",
            "length",
            "depth",
            "year_published",
            "thumbnail",
            "image",
            "language",
            "version_nickname",
        ],
        "dropna": ["game_id"],
    },
]

GAMES_INTEGER_COLUMNS = [
    "id",
    "min_players",
    "max_players",
    "playing_time",
    "min_playtime",
    "max_playtime",
    "min_age",
    "year_published",
    "num_ratings",
    "num_comments",
    "num_weights",
    "owned",
    "trading",
    "wanting",
    "wishing",
    "users_rated",
    "rank",
    "abstracts_rank",
    "cgs_rank",
    "childrens_games_rank",
    "family_games_rank",
    "party_games_rank",
    "strategy_games_rank",
    "thematic_rank",
    "wargames_rank",
]
GAMES_FLOAT_COLUMNS = [
    "average",
    "average_weight",
    "stddev",
    "median",
    "bayes_average",
]
GAMES_BOOLEAN_COLUMNS = ["is_expansion"]

RELATION_INTEGER_COLUMNS = {
    "mechanics": ["game_id", "boardgamemechanic_id"],
    "categories": ["game_id", "boardgamecategory_id"],
    "designers": ["game_id", "boardgamedesigner_id"],
    "artists": ["game_id", "boardgameartist_id"],
    "publishers": ["game_id", "boardgamepublisher_id"],
    "integrations": ["game_id", "boardgameintegration_id"],
    "implementations": ["game_id", "boardgameimplementation_id"],
    "compilations": ["game_id", "boardgamecompilation_id"],
    "expansions": ["game_id", "boardgameexpansion_id"],
    "families": ["game_id", "boardgamefamily_id"],
    "suggested_players": [
        "game_id",
        "player_count",
        "best",
        "recommended",
        "not_recommended",
        "game_total_votes",
        "player_count_total_votes",
        "recommendation_level",
    ],
    "language_dependence": [
        "game_id",
        "level_1",
        "level_2",
        "level_3",
        "level_4",
        "level_5",
        "total_votes",
        "language_dependency",
    ],
    "versions": ["game_id", "version_id", "year_published"],
}
RELATION_FLOAT_COLUMNS = {
    "versions": ["width", "length", "depth"],
}


def _prepare_games_dataframe(games_df: pd.DataFrame) -> pd.DataFrame:
    prepared = games_df.rename(columns=GAME_SOURCE_TO_TARGET)
    for source, target in GAME_SOURCE_TO_TARGET.items():
        if source not in games_df.columns:
            prepared[target] = None
    prepared = prepared[list(GAME_SOURCE_TO_TARGET.values())]
    prepared = prepared.drop_duplicates(subset=["id"], keep="first")
    return _normalize_dataframe_for_copy(
        prepared,
        integer_columns=GAMES_INTEGER_COLUMNS,
        float_columns=GAMES_FLOAT_COLUMNS,
        boolean_columns=GAMES_BOOLEAN_COLUMNS,
    )


def _prepare_relation_dataframe(spec: dict, frame: pd.DataFrame) -> pd.DataFrame:
    rename_map = spec.get("rename") or {}
    prepared = frame.rename(columns=rename_map)

    for column in spec["columns"]:
        if column not in prepared.columns:
            prepared[column] = None

    dropna_cols = spec.get("dropna") or []
    if dropna_cols:
        prepared = prepared.dropna(subset=dropna_cols)

    dedupe_on = spec.get("dedupe_on")
    if dedupe_on:
        prepared = prepared.drop_duplicates(subset=dedupe_on, keep="first")

    prepared = prepared[spec["columns"]]
    table_name = spec["table"]
    return _normalize_dataframe_for_copy(
        prepared,
        integer_columns=RELATION_INTEGER_COLUMNS.get(table_name, []),
        float_columns=RELATION_FLOAT_COLUMNS.get(table_name, []),
        boolean_columns=[],
    )


def _coerce_nullable_boolean(value):
    if pd.isna(value):
        return pd.NA
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(int(value))
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y"}:
        return True
    if text in {"0", "false", "f", "no", "n"}:
        return False
    return pd.NA


def _normalize_dataframe_for_copy(
    frame: pd.DataFrame,
    *,
    integer_columns: list[str],
    float_columns: list[str],
    boolean_columns: list[str],
) -> pd.DataFrame:
    normalized = frame.copy()

    for column in integer_columns:
        if column in normalized.columns:
            normalized[column] = pd.to_numeric(
                normalized[column],
                errors="coerce",
            ).astype("Int64")

    for column in float_columns:
        if column in normalized.columns:
            normalized[column] = pd.to_numeric(
                normalized[column],
                errors="coerce",
            )

    for column in boolean_columns:
        if column in normalized.columns:
            normalized[column] = (
                normalized[column].map(_coerce_nullable_boolean).astype("boolean")
            )

    return normalized


def _copy_dataframe(
    raw_connection, *, table: str, columns: list[str], frame: pd.DataFrame
) -> int:
    if frame.empty:
        return 0

    inserted = 0
    copy_sql = (
        f"COPY {table} ({', '.join(columns)}) FROM STDIN WITH (FORMAT csv, NULL '\\N')"
    )

    with raw_connection.cursor() as cursor:
        for start in range(0, len(frame), COPY_CHUNK_ROWS):
            chunk = frame.iloc[start : start + COPY_CHUNK_ROWS]
            output = io.StringIO()
            chunk.to_csv(
                output,
                index=False,
                header=False,
                na_rep="\\N",
            )
            output.seek(0)
            cursor.copy_expert(copy_sql, output)
            inserted += len(chunk)

    return inserted


def import_all_data_postgres(
    *,
    engine: Engine,
    data_dir: str,
    timestamp: int,
    logger,
) -> None:
    games_file = f"{data_dir}/processed_games_data_{timestamp}.csv"
    games_df = pd.read_csv(games_file, sep="|", escapechar="\\")
    games_df = _prepare_games_dataframe(games_df)

    raw_connection = engine.raw_connection()
    try:
        with raw_connection.cursor() as cursor:
            cursor.execute("SET LOCAL synchronous_commit TO OFF")
            cursor.execute("SET LOCAL statement_timeout TO 0")

        inserted_games = _copy_dataframe(
            raw_connection,
            table="games",
            columns=list(GAME_SOURCE_TO_TARGET.values()),
            frame=games_df,
        )
        logger.info("Inserted %s game rows", inserted_games)

        for spec in RELATION_SPECS:
            entity = spec["entity"]
            path = f"{data_dir}/processed_games_{entity}_{timestamp}.csv"
            try:
                frame = pd.read_csv(path, sep="|", escapechar="\\")
            except FileNotFoundError:
                logger.warning("File for %s not found, skipping...", entity)
                continue

            prepared = _prepare_relation_dataframe(spec, frame)
            inserted = _copy_dataframe(
                raw_connection,
                table=spec["table"],
                columns=spec["columns"],
                frame=prepared,
            )
            logger.info("Inserted %s rows into %s", inserted, spec["table"])

        raw_connection.commit()
    except Exception:
        raw_connection.rollback()
        raise
    finally:
        raw_connection.close()
