"""
BoardGameGeek (BGG) Ratings Crawler

This script crawls user ratings from BoardGameGeek.com.
This is the third script in the data collection pipeline and should be run after get_game_data.py.

Execution order:
1. get_ranks.py - Gets the current board game rankings
2. get_game_data.py - Gets detailed game information
3. get_ratings.py - Gets user ratings for each game

Usage:
    python get_ratings.py [--continue-from-last]
"""

from bs4 import BeautifulSoup
import requests
import pandas as pd
import logging
import math
import json
import os
from time import sleep, time
from pathlib import Path
import argparse
import bs4
import duckdb
import csv
from dotenv import load_dotenv
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

try:
    from ..common.logging_utils import build_log_handlers
except ImportError:
    from data_pipeline.src.common.logging_utils import build_log_handlers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=build_log_handlers("get_ratings.log"),
)
logger = logging.getLogger(__name__)

BATCH_REQUEST_TIMEOUT_SECONDS = 20
BGG_TOKEN_ENV_VAR = "BGG_TOKEN"


def _get_bgg_token() -> str:
    token = os.getenv(BGG_TOKEN_ENV_VAR, "").strip()
    if token:
        return token

    repo_root_dotenv = Path(__file__).resolve().parents[3] / ".env"
    if repo_root_dotenv.exists():
        load_dotenv(dotenv_path=repo_root_dotenv, override=False)
        token = os.getenv(BGG_TOKEN_ENV_VAR, "").strip()
        if token:
            return token

    return ""


def _build_bgg_auth_headers() -> dict[str, str]:
    token = _get_bgg_token()
    if not token:
        raise ValueError(
            f"Missing required {BGG_TOKEN_ENV_VAR} environment variable for BGG API auth."
        )
    return {"Authorization": f"Bearer {token}"}


@retry(
    retry=retry_if_exception_type(requests.RequestException),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
def _http_get_bgg_xml(url: str) -> requests.Response:
    response = requests.get(
        url,
        headers=_build_bgg_auth_headers(),
        timeout=BATCH_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response


def load_game_data_from_duckdb(duckdb_path: Path) -> pd.DataFrame:
    """Load boardgame_data records from DuckDB JSON payload storage."""
    con = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        payload_rows = con.execute(
            "SELECT payload_json FROM boardgame_data ORDER BY id"
        ).fetchall()
    finally:
        con.close()
    if not payload_rows:
        return pd.DataFrame()
    records = [json.loads(row[0]) for row in payload_rows]
    return pd.DataFrame(records)


def save_game_data_to_duckdb(boardgame_data: pd.DataFrame, save_path: Path) -> None:
    """Persist updated boardgame_data snapshot in DuckDB JSON payload format."""
    con = duckdb.connect(str(save_path))
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS boardgame_data (
            id BIGINT PRIMARY KEY,
            payload_json TEXT
        );
        """
    )
    rows = [
        {"id": int(record["id"]), "payload_json": json.dumps(record)}
        for record in boardgame_data.to_dict(orient="records")
    ]
    df_rows = pd.DataFrame(rows)
    con.register("game_data_tmp", df_rows)
    con.execute("DELETE FROM boardgame_data;")
    con.execute(
        """
        INSERT INTO boardgame_data (id, payload_json)
        SELECT id, payload_json
        FROM game_data_tmp;
        """
    )
    con.unregister("game_data_tmp")
    con.close()


def get_boardgame_ratings(
    boardgame_data: pd.DataFrame,
    boardgame_ratings: pd.DataFrame = None,
    ratings_store_path: Path | None = None,
    batch_saves: bool = False,
    batch_size: int = 20,
    log_level: str = "INFO",
    keep_partial_ratings: bool = False,
    update_numratings: bool = False,
):
    """
    Fetch user ratings for each board game from BGG API.
    The BGG API has a limit of 20 IDs per request, so we process in batches.

    Args:
        boardgame_data (pd.DataFrame): DataFrame from get_boardgame_data()
        boardgame_ratings (pd.DataFrame, optional): Existing ratings data to update
        ratings_store_path (Path, optional): Ratings DuckDB file path to write/update
        batch_saves (bool): Whether to save data after each batch
        batch_size (int): Number of games to process in each batch. BGG API has a limit of 20 IDs per request.
        log_level (str): Logging level for this function
        drop_partial_ratings (bool): Whether to drop games with partial ratings
        update_numratings (bool): Whether to update number of ratings for games with missing ratings

    Returns:
        pd.DataFrame: DataFrame containing user ratings
    """
    # Set logging level for this function
    current_level = logger.level
    logger.setLevel(getattr(logging, log_level.upper()))

    project_root = Path(__file__).resolve().parents[3]
    ratings_dir = project_root / "data" / "ingest" / "ratings"
    game_data_dir = project_root / "data" / "ingest" / "game_data"
    ratings_dir.mkdir(parents=True, exist_ok=True)
    game_data_dir.mkdir(parents=True, exist_ok=True)

    # Initialize DuckDB persistent store for ratings
    if ratings_store_path is None:
        query_time = int(time())
        ratings_store_path = ratings_dir / f"boardgame_ratings_{query_time}.duckdb"
    duckdb_path = ratings_store_path
    logger.info("Using ratings DuckDB store: %s", duckdb_path)
    con = duckdb.connect(str(duckdb_path))
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS boardgame_ratings (
            game_id BIGINT,
            rating_round DOUBLE,
            username TEXT
        );
        """
    )
    # Index to speed up de-dup checks
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_boardgame_ratings ON boardgame_ratings(game_id, rating_round, username);"
    )

    boardgame_master_dict = {}
    boardgame_data_ratings = boardgame_data.loc[
        boardgame_data["numratings"] > 100
    ].sort_values(by="numratings", ascending=True)
    boardgame_ids = boardgame_data_ratings["id"].tolist()
    # Check if there are any ids which have not had all their ratings pulled down yet
    if boardgame_ratings is not None:
        df_ratings_len = boardgame_ratings.copy()
        df_ratings_len = df_ratings_len.drop(columns=["id"])
        df_ratings_len = df_ratings_len.fillna("")
        for col in df_ratings_len.columns:
            df_ratings_len[col] = df_ratings_len[col].apply(len)
        df_ratings_pulled = pd.DataFrame(
            {
                "id": boardgame_ratings["id"].tolist(),
                "ratings_pulled": df_ratings_len.sum(axis=1).tolist(),
            }
        )
        boardgame_data_ratings = boardgame_data_ratings.merge(
            df_ratings_pulled, on="id", how="left"
        )
        completed_ids = boardgame_data_ratings.loc[
            (
                boardgame_data_ratings["ratings_pulled"]
                - boardgame_data_ratings["numratings"]
            )
            / (boardgame_data_ratings["numratings"])
            >= -0.1,
            "id",
        ].tolist()
        logger.info(
            f"Found {len(completed_ids)} boardgames with all ratings already pulled to completion"
        )
        boardgame_ids = list(set(boardgame_ids).difference(set(completed_ids)))
        # reorder boardgame_ids to match boardgame_data_ratings
        boardgame_ids = boardgame_data_ratings.loc[
            boardgame_data_ratings["id"].isin(boardgame_ids), "id"
        ].tolist()
        df_missing_ratings = boardgame_data_ratings.loc[
            (
                boardgame_data_ratings["ratings_pulled"]
                - boardgame_data_ratings["numratings"]
            )
            / (boardgame_data_ratings["numratings"])
            < -0.1
        ]
        logger.info(
            f"Found {df_missing_ratings.shape[0]} boardgames with missing ratings"
        )
        if not keep_partial_ratings:
            logger.info("Dropping partial ratings")
            boardgame_ratings = boardgame_ratings.loc[
                ~(boardgame_ratings["id"].isin(df_missing_ratings["id"]))
            ]
            # Also remove any partial rows for these games from the DuckDB snapshot
            # so interim exports built from DuckDB cannot include half-complete data
            if df_missing_ratings.shape[0] > 0:
                ids_to_drop = df_missing_ratings["id"].dropna().astype("int64").tolist()
                if len(ids_to_drop) > 0:
                    try:
                        con.register(
                            "to_delete_games", pd.DataFrame({"game_id": ids_to_drop})
                        )
                        con.execute(
                            """
                            DELETE FROM boardgame_ratings
                            WHERE game_id IN (SELECT game_id FROM to_delete_games);
                            """
                        )
                        con.unregister("to_delete_games")
                        logger.info(
                            f"Removed {len(ids_to_drop)} game(s) with partial ratings from DuckDB"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to delete partial ratings from DuckDB: {str(e)}"
                        )
        else:
            logger.info(
                "Keeping partial ratings and will continue to pull down the missing ratings"
            )

        df_ratings_tmp = boardgame_ratings.copy().set_index("id")
        df_ratings_tmp.index.name = None
        boardgame_master_dict = df_ratings_tmp.to_dict(orient="index")

        if keep_partial_ratings and df_missing_ratings.shape[0] > 0:
            for _, row in df_missing_ratings.iterrows():
                ratings_count_dict = {row["id"]: row["numratings"]}
                max_ratings_page = math.ceil(row["numratings"] / 100)
                start_page = int(row["ratings_pulled"] / 100) + 1
                boardgame_master_dict = iterate_through_ratings_pages(
                    boardgame_master_dict=boardgame_master_dict,
                    max_ratings_page=max_ratings_page,
                    ratings_count_dict=ratings_count_dict,
                    start_page=start_page,
                    batch_saves=batch_saves,
                    duckdb_conn=con,
                )
                logger.info(f"Successfully completed fetching ratings for {row['id']}")
            df_ratings = (
                pd.DataFrame()
                .from_dict(data=boardgame_master_dict, orient="index")
                .reset_index(names="id")
            )
            boardgame_ids = list(
                set(boardgame_ids).difference(set(df_ratings["id"].tolist()))
            )

        # Update numratings if requested
        if update_numratings:
            game_data_save_path = game_data_dir / f"boardgame_data_{query_time}.duckdb"
            logger.info("Updating number of ratings for games with missing ratings")
            for batch_num in range(math.ceil(len(boardgame_ids) / batch_size)):
                logger.info(
                    f"Processing numratings batch {batch_num} of {math.ceil(len(boardgame_ids) / batch_size)}"
                )
                batch_ids = boardgame_ids[
                    batch_num * batch_size : (batch_num + 1) * batch_size
                ]
                batch_ids = [str(x) for x in batch_ids]
                logger.debug(f"Processing boardgame IDs for numratings: {batch_ids}")

                bg_info_url = f"https://boardgamegeek.com/xmlapi2/thing?type=boardgame&ratingcomments=1&id={','.join(batch_ids)}"
                bgg_response = _http_get_bgg_xml(bg_info_url)
                soup_xml = BeautifulSoup(bgg_response.content, "xml")
                games_xml_list = soup_xml.find_all(
                    "item", attrs={"type": ["boardgame", "boardgameexpansion"]}
                )
                if len(games_xml_list) == 0:
                    raise RuntimeError(
                        f"BGG API returned zero items for batch URL: {bg_info_url}"
                    )

                for game_xml in games_xml_list:
                    game_id = int(game_xml["id"])
                    if game_xml.find("comments") is not None:
                        boardgame_data.loc[
                            boardgame_data["id"] == game_id, "numratings"
                        ] = int(game_xml.find("comments")["totalitems"])
                    else:
                        boardgame_data.loc[
                            boardgame_data["id"] == game_id, "numratings"
                        ] = 0
                if batch_saves and (batch_num + 1) % 20 == 0:
                    logger.info(f"Saving batch {batch_num} data")
                    save_game_data_to_duckdb(boardgame_data, game_data_save_path)
                    logger.info(
                        f"Saved batch {batch_num} data to {game_data_save_path}"
                    )

                sleep(1)

            # Save updated game data
            save_game_data_to_duckdb(boardgame_data, game_data_save_path)
            logger.info(f"Saved updated game data to {game_data_save_path}")
            boardgame_data_ratings = boardgame_data.loc[
                boardgame_data["numratings"] > 100
            ].sort_values(by="numratings", ascending=False)

    logger.info(f"Starting to fetch ratings for {len(boardgame_ids)} boardgames")

    for batch_num in range(math.ceil(len(boardgame_ids) / batch_size)):
        logger.info(
            f"Processing batch {batch_num + 1} of {math.ceil(len(boardgame_ids) / batch_size)}"
        )
        batch_ids = boardgame_ids[batch_num * batch_size : (batch_num + 1) * batch_size]
        df_batch_games = boardgame_data_ratings.loc[
            boardgame_data_ratings["id"].isin(batch_ids)
        ]
        ratings_count_dict = pd.Series(
            df_batch_games["numratings"].values,
            index=df_batch_games["id"],
        ).to_dict()
        max_ratings_page = math.ceil(max(ratings_count_dict.values()) / 100)
        logger.info(
            f"Processing {max_ratings_page} rating pages for batch {batch_num + 1}"
        )
        boardgame_master_dict = iterate_through_ratings_pages(
            boardgame_master_dict=boardgame_master_dict,
            max_ratings_page=max_ratings_page,
            ratings_count_dict=ratings_count_dict,
            batch_saves=batch_saves,
            duckdb_conn=con,
        )

    if len(boardgame_ids) > 0:
        logger.info(
            "Successfully completed fetching all ratings to DuckDB state store."
        )
    else:
        logger.warning("No ratings were fetched")

    # Restore original logging level
    logger.setLevel(current_level)
    con.close()


def iterate_through_ratings_pages(
    boardgame_master_dict: dict,
    max_ratings_page: int,
    ratings_count_dict: dict,
    start_page: int = 1,
    batch_saves: bool = False,
    duckdb_conn: duckdb.DuckDBPyConnection = None,
):
    """
    Helper function to iterate through paginated rating data from BGG API.

    Args:
        boardgame_master_dict (dict): Dictionary to store rating data
        max_ratings_page (int): Maximum number of rating pages to process. Derived from the number of ratings for each game.
        ratings_count_dict (dict): Dictionary mapping game IDs to number of ratings
        start_page (int): Page number to start processing from
        batch_saves (bool): Retained for API compatibility; DuckDB writes are incremental.

    Returns:
        dict: Updated dictionary containing rating data
    """
    for page_num in range(start_page, max_ratings_page + 1):
        # Only grab the pages for games which have enough ratings to be on the page num
        batch_ids_ratings = [
            str(x)
            for x in ratings_count_dict.keys()
            if math.ceil(ratings_count_dict[x] / 100) >= page_num
        ]
        bg_rating_url = f"https://boardgamegeek.com/xmlapi2/thing?type=boardgame&ratingcomments=1&pagesize=100&page={page_num}&id={','.join(batch_ids_ratings)}"
        bgg_rating_response = _http_get_bgg_xml(bg_rating_url)
        soup_rating_xml = BeautifulSoup(bgg_rating_response.content, "xml")
        ratings_xml_list = soup_rating_xml.find_all("item", attrs={"type": "boardgame"})
        if len(ratings_xml_list) == 0:
            raise RuntimeError(
                f"BGG API returned zero rating items for page URL: {bg_rating_url}"
            )

        rows_for_page = []
        for game_xml in ratings_xml_list:
            game_id = int(game_xml["id"])
            if game_id not in boardgame_master_dict:
                boardgame_master_dict[game_id] = {}
            per_game_new = parse_ratings_to_dict(game_xml)
            for rating_round, users in per_game_new.items():
                if rating_round not in boardgame_master_dict[game_id]:
                    boardgame_master_dict[game_id][rating_round] = list(users)
                else:
                    boardgame_master_dict[game_id][rating_round].extend(users)
            for rating_round, users in per_game_new.items():
                for username in users:
                    rows_for_page.append((game_id, float(rating_round), username))

        if duckdb_conn is not None and len(rows_for_page) > 0:
            df_insert = pd.DataFrame(
                rows_for_page, columns=["game_id", "rating_round", "username"]
            )
            df_insert = df_insert.drop_duplicates()
            duckdb_conn.register("ratings_tmp", df_insert)
            duckdb_conn.execute(
                """
                INSERT INTO boardgame_ratings
                SELECT game_id, rating_round, username
                FROM ratings_tmp t
                WHERE NOT EXISTS (
                    SELECT 1 FROM boardgame_ratings b
                    WHERE b.game_id = t.game_id
                      AND b.rating_round = t.rating_round
                      AND b.username = t.username
                );
                """
            )
            duckdb_conn.unregister("ratings_tmp")

        if page_num % 100 == 0:
            logger.info(f"Processed ratings page {page_num} of {max_ratings_page}")
        sleep(1)
    return boardgame_master_dict


def parse_ratings_to_dict(game_xml: bs4.element.Tag) -> dict:
    """
    Parse a game's XML into {rating_round_str: [usernames...]}
    without mutating an existing aggregate.
    """
    game_dict: dict = {}
    ratings_list = game_xml.find_all("comment")
    for rating in ratings_list:
        rating_round = str(round(2 * float(rating["rating"])) / 2)
        if rating_round not in game_dict:
            game_dict[rating_round] = [rating["username"]]
        else:
            game_dict[rating_round].append(rating["username"])
    return game_dict


def build_wide_ratings_df_from_duckdb(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """
    Build the wide ratings DataFrame (id + rating bucket columns of username lists)
    from the persistent DuckDB table.
    """
    df_long = con.execute(
        """
        SELECT game_id, rating_round, list(username) AS usernames
        FROM boardgame_ratings
        GROUP BY game_id, rating_round
        """
    ).fetch_df()

    df_long["usernames"] = df_long["usernames"].apply(lambda x: x.tolist())
    df_wide = df_long.pivot(index="game_id", columns="rating_round", values="usernames")
    df_wide.columns.name = None
    df_wide = df_wide.reset_index(names="id")
    df_wide.columns = df_wide.columns.astype(str)

    # master: dict = {}
    # for _, row in df_long.iterrows():
    #     game_id = int(row["game_id"])
    #     rating_key = str(row["rating_round"])  # keep columns as str like prior format
    #     usernames = row["usernames"]
    #     # DuckDB may return a list type for list_agg
    #     if isinstance(usernames, list):
    #         usernames_list = usernames
    #     else:
    #         usernames_list = [usernames]
    #     if game_id not in master:
    #         master[game_id] = {}
    #     master[game_id][rating_key] = usernames_list

    # if len(master) == 0:
    #     return pd.DataFrame(columns=["id"])  # empty

    # df_wide = (
    #     pd.DataFrame()
    #     .from_dict(data=master, orient="index")
    #     .reset_index(names="id")
    # )
    return df_wide


def main():
    """Main function to get board game ratings."""
    try:
        parser = argparse.ArgumentParser(description="Get board game ratings from BGG")
        parser.add_argument(
            "--continue-from-last",
            action="store_true",
            help="Continue from the most recent output file",
        )
        parser.add_argument(
            "--update-numratings",
            action="store_true",
            help="Update number of ratings for games with missing ratings",
        )
        parser.add_argument(
            "--keep-partial-ratings",
            action="store_true",
            help="Keep games with partial ratings instead of dropping them",
        )
        args = parser.parse_args()

        # Get the most recent game_ranks file
        project_root = Path(__file__).resolve().parents[3]
        ranks_dir = project_root / "data" / "ingest" / "ranks"
        game_data_dir = project_root / "data" / "ingest" / "game_data"
        ratings_dir = project_root / "data" / "ingest" / "ratings"
        ratings_dir.mkdir(parents=True, exist_ok=True)
        game_ranks_files = list(ranks_dir.glob("boardgame_ranks_*.csv"))
        if not game_ranks_files:
            raise FileNotFoundError("No game ranks files found")
        latest_ranks = max(game_ranks_files, key=lambda x: x.stat().st_mtime)
        logger.info(f"Using game ranks file: {latest_ranks}")
        df_ranks = pd.read_csv(
            latest_ranks,
            sep="|",
            escapechar="\\",
            quoting=csv.QUOTE_NONE,
            usecols=["id", "is_expansion"],
        )
        non_expansion_ids = df_ranks.loc[df_ranks["is_expansion"] == 0, "id"].tolist()

        # Get the most recent game data file (DuckDB only).
        game_files = list(game_data_dir.glob("boardgame_data_*.duckdb"))
        if not game_files:
            raise FileNotFoundError("No game data files found")

        latest_games = max(game_files, key=lambda x: x.stat().st_mtime)
        logger.info(f"Using game data file: {latest_games}")

        # Read game data
        df_games = load_game_data_from_duckdb(latest_games)
        df_games = df_games.loc[df_games["id"].isin(non_expansion_ids)]

        # Get existing ratings if continuing (DuckDB only)
        existing_ratings = None
        ratings_store_path = ratings_dir / f"boardgame_ratings_{int(time())}.duckdb"
        if args.continue_from_last:
            ratings_files = list(ratings_dir.glob("boardgame_ratings_*.duckdb"))
            if ratings_files:
                latest_ratings = max(ratings_files, key=lambda x: x.stat().st_mtime)
                ratings_store_path = latest_ratings
                logger.info("Continuing from DuckDB ratings at: %s", latest_ratings)
                con = duckdb.connect(str(latest_ratings))
                try:
                    existing_ratings = build_wide_ratings_df_from_duckdb(con)
                finally:
                    con.close()
                logger.info("Pulled ratings from DuckDB ratings at: %s", latest_ratings)
            else:
                logger.info(
                    "No prior ratings DuckDB file found; starting fresh at %s",
                    ratings_store_path,
                )
        else:
            logger.info("Starting fresh ratings DuckDB at: %s", ratings_store_path)

        # Get ratings
        get_boardgame_ratings(
            boardgame_data=df_games,
            boardgame_ratings=existing_ratings,
            ratings_store_path=ratings_store_path,
            batch_saves=True,
            update_numratings=args.update_numratings,
            keep_partial_ratings=args.keep_partial_ratings,
        )
        logger.info("Successfully completed getting board game ratings")

    except Exception as e:
        logger.error(f"Error getting board game ratings: {str(e)}")
        raise


if __name__ == "__main__":
    main()
