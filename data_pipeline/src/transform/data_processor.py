"""
Data Processor for Board Game Recommender

This script processes the outputs from the crawler and formats them for import into the backend database.
It combines board game rankings and detailed game data into a format that matches the backend models.
"""

import pandas as pd
from pathlib import Path
from typing import List, Optional, cast
import logging
import time
import csv
import argparse

try:
    from ..common.logging_utils import build_log_handlers
except ImportError:
    from data_pipeline.src.common.logging_utils import build_log_handlers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=build_log_handlers("data_processor.log"),
)
logger = logging.getLogger(__name__)

# Resolve project root from `data_pipeline/src/transform`.
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def save_basic_info(
    df_merged: pd.DataFrame, output_file_base: str, timestamp: int
) -> None:
    """
    Save the basic info for the games to a csv file.
    Args:
        df_merged (pd.DataFrame): The dataframe to save
        output_file_base (str): The base path to save the file
        timestamp (int): The timestamp to use for the file name
    """
    int_cols = [
        "yearpublished",
        "rank",
        "usersrated",
        "is_expansion",
        "abstracts_rank",
        "cgs_rank",
        "childrensgames_rank",
        "familygames_rank",
        "partygames_rank",
        "strategygames_rank",
        "thematic_rank",
        "wargames_rank",
        "minplayers",
        "maxplayers",
        "playingtime",
        "minplaytime",
        "maxplaytime",
        "minage",
        "owned",
        "trading",
        "wanting",
        "wishing",
        "numcomments",
        "numweights",
        "numratings",
    ]

    float_cols = [
        "bayesaverage",
        "average",
        "stddev",
        "median",
        "averageweight",
    ]

    str_cols = [
        "name",
        "thumbnail",
        "image",
        "description",
    ]

    # Games with rank 0 should be nan
    df_merged.loc[df_merged["rank"] == 0, "rank"] = pd.NA

    # Covert columns to int
    for col in int_cols:
        df_merged[col] = df_merged[col].fillna(value=pd.NA).astype(pd.Int64Dtype())

    # Convert columns to float
    for col in float_cols:
        df_merged[col] = df_merged[col].fillna(value=pd.NA).astype(pd.Float64Dtype())

    # Save the int, float, and str columns to csv
    output_file_data = f"{output_file_base}_data_{timestamp}.csv"
    df_merged[["id"] + str_cols + int_cols + float_cols].to_csv(
        output_file_data,
        index=False,
        sep="|",
        escapechar="\\",
        quoting=csv.QUOTE_NONE,
    )
    logger.info(
        f"Successfully saved basic info for {len(df_merged)} games to {output_file_data}"
    )


def save_dict_id_cols(
    df_merged: pd.DataFrame, output_file_base: str, timestamp: int
) -> None:
    """
    Save the dict_id_cols for the games to a csv file.
    Args:
        df_merged (pd.DataFrame): The dataframe to save
        output_file_base (str): The base path to save the file
        timestamp (int): The timestamp to use for the file name
    """
    dict_id_cols = [
        "boardgamecategory",
        "boardgamemechanic",
        "boardgamefamily",
        "boardgameexpansion",
        "boardgameartist",
        "boardgamecompilation",
        "boardgameimplementation",
        "boardgamedesigner",
        "boardgamepublisher",
        "boardgameintegration",
    ]

    # Save the dict_id_cols to csv
    for col in dict_id_cols:
        df_dict_id = pd.DataFrame(
            [
                {"game_id": row_id, f"{col}_id": k, f"{col}_name": v}
                for row_id, d in zip(df_merged["id"], df_merged[col])
                if isinstance(d, dict)  # ensure it's a dict
                for k, v in d.items()
            ]
        )
        df_dict_id[f"{col}_id"] = df_dict_id[f"{col}_id"].astype(int)
        output_file_dict_id = f"{output_file_base}_{col}_{timestamp}.csv"
        df_dict_id.to_csv(
            output_file_dict_id,
            index=False,
            sep="|",
            escapechar="\\",
            quoting=csv.QUOTE_NONE,
        )
        logger.info(
            f"Successfully saved {col} for {len(df_dict_id)} games to {output_file_dict_id}"
        )


def save_suggested_num_players(
    df_merged: pd.DataFrame, output_file_base: str, timestamp: int
) -> None:
    """
    Extract player count recs from the dataframe.
    Args:
        df_merged (pd.DataFrame): The dataframe to save
        output_file_base (str): The base path to save the file
        timestamp (int): The timestamp to use for the file name
    """
    df_sugg_num_players = df_merged.loc[
        ~(df_merged["suggested_numplayers"] == {}), ["id", "suggested_numplayers"]
    ]
    df_sugg_num_players["game_total_votes"] = df_sugg_num_players[
        "suggested_numplayers"
    ].apply(lambda x: x["total_votes"])
    df_sugg_num_players = df_sugg_num_players.loc[
        df_sugg_num_players["game_total_votes"] > 10
    ]
    col = "suggested_numplayers"
    df_exploded = pd.DataFrame(
        [
            {"id": row_id, col: k, "votes": v}
            for row_id, d in zip(df_sugg_num_players["id"], df_sugg_num_players[col])
            if isinstance(d, dict)  # ensure it's a dict
            for k, v in d.items()
        ]
    )
    votes_data = cast(pd.Series, df_exploded["votes"]).tolist()
    df_exploded = pd.concat(
        [df_exploded.drop(columns="votes"), pd.json_normalize(votes_data)],
        axis=1,
    )
    df_exploded = df_exploded.loc[
        (df_exploded[col] != "total_votes")
        & ~(df_exploded[col].str.contains("+", regex=False))
    ]
    df_exploded = df_exploded.merge(
        df_sugg_num_players[["id", "game_total_votes"]], on="id", how="left"
    )
    df_exploded.columns = [x.lower().replace(" ", "_") for x in df_exploded.columns]
    for col in df_exploded.columns:
        df_exploded[col] = df_exploded[col].astype(pd.Int64Dtype())
    df_exploded["recommendation_level"] = df_exploded[
        ["best", "recommended", "not_recommended"]
    ].idxmax(axis=1)
    df_exploded = df_exploded.rename(
        columns={"suggested_numplayers": "player_count", "id": "game_id"}
    )
    output_file_suggested_num_players = (
        f"{output_file_base}_suggested_num_players_{timestamp}.csv"
    )
    df_exploded.to_csv(
        output_file_suggested_num_players,
        index=False,
        sep="|",
        escapechar="\\",
        quoting=csv.QUOTE_NONE,
    )
    logger.info(
        f"Successfully saved {len(df_exploded)} suggested num players to {output_file_suggested_num_players}"
    )


def save_versions(
    df_merged: pd.DataFrame, output_file_base: str, timestamp: int
) -> None:
    """
    Save the versions for the games to a csv file.
    Args:
        df_merged (pd.DataFrame): The dataframe to save
        output_file_base (str): The base path to save the file
        timestamp (int): The timestamp to use for the file name
    """
    df_versions = (
        df_merged.loc[df_merged["versions"].notna(), ["id", "versions"]]
        .explode("versions")
        .reset_index(drop=True)
    )
    df_versions = pd.concat(
        [
            df_versions.drop(columns="versions"),
            pd.json_normalize(df_versions["versions"]),
        ],
        axis=1,
    )
    df_versions = df_versions.rename(columns={"id": "game_id"})
    output_file_versions = f"{output_file_base}_versions_{timestamp}.csv"
    df_versions.to_csv(
        output_file_versions,
        index=False,
        sep="|",
        escapechar="\\",
        quoting=csv.QUOTE_NONE,
    )
    logger.info(
        f"Successfully saved {len(df_versions)} versions to {output_file_versions}"
    )


def save_language_dependence(
    df_merged: pd.DataFrame, output_file_base: str, timestamp: int
) -> None:
    """
    Save the language dependence for the games to a csv file.
    Args:
        df_merged (pd.DataFrame): The dataframe to save
        output_file_base (str): The base path to save the file
        timestamp (int): The timestamp to use for the file name
    """
    df_lang_dep = df_merged.loc[
        ~(df_merged["language_dependence"] == {}), ["id", "language_dependence"]
    ]
    df_lang_dep["game_total_votes"] = df_lang_dep["language_dependence"].apply(
        lambda x: x["total_votes"]
    )
    df_lang_dep = df_lang_dep.loc[df_lang_dep["game_total_votes"] > 10]
    col = "language_dependence"
    df_exploded = pd.DataFrame(
        [
            {"id": row_id, col: k, "votes": v}
            for row_id, d in zip(df_lang_dep["id"], df_lang_dep[col])
            if isinstance(d, dict)  # ensure it's a dict
            for k, v in d.items()
        ]
    )
    df_exploded = df_exploded.loc[(df_exploded[col] != "total_votes")]
    df_exploded["language_dependence"] = df_exploded["language_dependence"].astype(int)
    df_min = (
        df_exploded[["id", "language_dependence"]]
        .groupby("id")
        .min()
        .reset_index()
        .rename(columns={"language_dependence": "lang_min"})
    )
    df_exploded = df_exploded.merge(df_min, how="left", on="id")
    df_exploded["language_dependence_norm"] = (
        df_exploded["language_dependence"] - df_exploded["lang_min"] + 1
    )
    df_exploded = df_exploded.pivot(
        index="id", columns="language_dependence_norm", values="votes"
    )
    df_exploded["total_votes"] = df_exploded.sum(axis=1)
    df_exploded["language_dependency"] = df_exploded[[1, 2, 3, 4, 5]].idxmax(axis=1)
    df_exploded = df_exploded.reset_index()
    df_exploded.columns.name = None
    output_file_language_dependence = (
        f"{output_file_base}_language_dependence_{timestamp}.csv"
    )
    df_exploded.to_csv(
        output_file_language_dependence,
        index=False,
        sep="|",
        escapechar="\\",
        quoting=csv.QUOTE_NONE,
    )
    logger.info(
        f"Successfully saved {len(df_exploded)} language dependence to {output_file_language_dependence}"
    )


def combine_crawler_data(
    ranks_file: str,
    data_file: str,
    output_file_base: str,
    timestamp: int,
    exclude_ids: Optional[List[int]] = None,
) -> None:
    """
    Combine board game rankings and detailed data into a format for backend import.

    Args:
        ranks_file (str): Path to the board game rankings CSV file
        data_file (str): Path to the board game data parquet file
        output_file_base (str): Base path to save the combined data
        timestamp (int): Unix timestamp for the output file
        exclude_ids (List[int]): List of game IDs to exclude from the data
    """
    logger.info("Starting data combination process")

    # Read the data files
    try:
        df_ranks = pd.read_csv(
            ranks_file, sep="|", escapechar="\\", quoting=csv.QUOTE_NONE
        )
        df_data = pd.read_parquet(data_file)
        logger.info(
            f"Successfully loaded {len(df_ranks)} rankings and {len(df_data)} detailed records"
        )
    except Exception as e:
        logger.error(f"Error reading input files: {str(e)}")
        raise

    # Drop columns from ranks that we don't want to merge
    df_ranks = df_ranks.drop(columns=["queried_at_utc"])

    # Merge rankings data with game data
    df_merged = pd.merge(df_data, df_ranks, on="id", how="inner")

    # Filter out excluded games
    if exclude_ids:
        df_merged = df_merged[~df_merged["id"].isin(exclude_ids)]
    df_merged = cast(pd.DataFrame, df_merged)

    # Save the basic info
    save_basic_info(df_merged, output_file_base, timestamp)

    # Save the dict_id_cols
    save_dict_id_cols(df_merged, output_file_base, timestamp)

    # Save the suggested num players
    save_suggested_num_players(df_merged, output_file_base, timestamp)

    # Save the versions
    save_versions(df_merged, output_file_base, timestamp)

    # Save the language dependence
    save_language_dependence(df_merged, output_file_base, timestamp)


def main():
    """Main function to process the most recent data pipeline outputs."""
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Process board game data from pipeline outputs."
    )
    parser.add_argument(
        "--exclude-expansions",
        action="store_true",
        help="Exclude board game expansions from the output",
    )
    args = parser.parse_args()

    # Get the data directory using the project root
    data_dir = PROJECT_ROOT / "data" / "pipeline"
    save_dir = PROJECT_ROOT / "data" / "processed"

    # Find the most recent ranks file
    ranks_files = list(data_dir.glob("boardgame_ranks_*.csv"))
    if not ranks_files:
        raise FileNotFoundError(f"No board game ranks files found in {data_dir}")
    latest_ranks = max(ranks_files, key=lambda x: x.stat().st_mtime)

    # Find the most recent data file
    data_files = list(data_dir.glob("boardgame_data_*.parquet"))
    if not data_files:
        raise FileNotFoundError(f"No board game data files found in {data_dir}")
    latest_data = max(data_files, key=lambda x: x.stat().st_mtime)

    # Set output file path with Unix timestamp
    timestamp = int(time.time())
    output_file_base = save_dir / "processed_games"

    # Read the ranks file to check for expansions if needed
    if args.exclude_expansions:
        df_ranks = pd.read_csv(
            latest_ranks, sep="|", escapechar="\\", quoting=csv.QUOTE_NONE
        )
        expansion_ids = df_ranks[df_ranks["is_expansion"] == 1]["id"].tolist()
        logger.info(f"Found {len(expansion_ids)} expansion games")
    else:
        expansion_ids = None

    # Process the data
    combine_crawler_data(
        ranks_file=str(latest_ranks),
        data_file=str(latest_data),
        output_file_base=str(output_file_base),
        timestamp=timestamp,
        exclude_ids=expansion_ids,
    )


if __name__ == "__main__":
    main()
