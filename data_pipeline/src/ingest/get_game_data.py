"""
BoardGameGeek (BGG) Game Data Crawler

This script crawls detailed game information from BoardGameGeek.com.
This is the second script in the data collection pipeline and should be run after get_ranks.py.

Execution order:
1. get_ranks.py - Gets the current board game rankings
2. get_game_data.py - Gets detailed game information
3. get_ratings.py - Gets user ratings for each game

Usage:
    python get_game_data.py [--continue-from-last]
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
import csv
import duckdb
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
    handlers=build_log_handlers("get_game_data.log"),
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


def _initialize_game_data_store(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS boardgame_data (
            id BIGINT PRIMARY KEY,
            payload_json TEXT
        );
        """
    )


def _upsert_game_batch(
    conn: duckdb.DuckDBPyConnection, game_dicts: list[dict[str, object]]
) -> None:
    if not game_dicts:
        return
    rows = [
        {"id": int(game_dict["id"]), "payload_json": json.dumps(game_dict)}
        for game_dict in game_dicts
    ]
    df_rows = pd.DataFrame(rows)
    conn.register("game_data_tmp", df_rows)
    conn.execute(
        """
        INSERT OR REPLACE INTO boardgame_data (id, payload_json)
        SELECT id, payload_json
        FROM game_data_tmp;
        """
    )
    conn.unregister("game_data_tmp")


def _load_completed_ids(conn: duckdb.DuckDBPyConnection) -> set[int]:
    completed_rows = conn.execute("SELECT id FROM boardgame_data").fetchall()
    return {int(row[0]) for row in completed_rows}


def _load_game_data_from_store(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    payload_rows = conn.execute(
        "SELECT payload_json FROM boardgame_data ORDER BY id"
    ).fetchall()
    if not payload_rows:
        return pd.DataFrame()
    records = [json.loads(row[0]) for row in payload_rows]
    return pd.DataFrame(records)


def _seed_store_from_dataframe(
    conn: duckdb.DuckDBPyConnection, boardgame_data: pd.DataFrame | None
) -> None:
    if boardgame_data is None:
        return
    row_count = conn.execute("SELECT COUNT(*) FROM boardgame_data").fetchone()[0]
    if row_count > 0:
        return
    seed_dicts = boardgame_data.to_dict(orient="records")
    _upsert_game_batch(conn, seed_dicts)


def _run_game_data_ingest(
    boardgame_ranks: pd.DataFrame,
    boardgame_data: pd.DataFrame | None,
    existing_store_path: Path | None,
    batch_saves: bool,
    batch_size: int,
    save_every_n_batches: int,
    log_level: str,
    simple_mode: bool,
) -> pd.DataFrame:
    current_level = logger.level
    logger.setLevel(getattr(logging, log_level.upper()))

    logger.info("Starting to fetch data for %d boardgames", len(boardgame_ranks))
    query_time = int(time())
    data_dir = Path(__file__).resolve().parents[3] / "data" / "ingest" / "game_data"
    data_dir.mkdir(parents=True, exist_ok=True)

    filename_prefix = "boardgame_simple_data" if simple_mode else "boardgame_data"
    save_path = (
        existing_store_path or data_dir / f"{filename_prefix}_{query_time}.duckdb"
    )
    conn = duckdb.connect(str(save_path))
    _initialize_game_data_store(conn)
    _seed_store_from_dataframe(conn, boardgame_data)

    try:
        completed_ids = _load_completed_ids(conn)
        boardgame_ids = [
            int(game_id)
            for game_id in boardgame_ranks["id"].tolist()
            if int(game_id) not in completed_ids
        ]
        logger.info("Found %d new boardgames to process", len(boardgame_ids))

        total_batches = (
            math.ceil(len(boardgame_ids) / batch_size) if boardgame_ids else 0
        )
        for batch_num in range(total_batches):
            logger.info("Processing batch %d of %d", batch_num + 1, total_batches)
            batch_ids = boardgame_ids[
                batch_num * batch_size : (batch_num + 1) * batch_size
            ]
            batch_id_strings = [str(game_id) for game_id in batch_ids]
            bg_info_url = (
                "https://boardgamegeek.com/xmlapi2/thing"
                "?type=boardgame,boardgameexpansion&stats=1"
                "&versions=1&ratingcomments=1&pagesize=100&page=1"
                f"&id={','.join(batch_id_strings)}"
            )
            if simple_mode:
                bg_info_url = (
                    "https://boardgamegeek.com/xmlapi2/thing"
                    "?type=boardgame,boardgameexpansion&stats=1"
                    "&ratingcomments=1&pagesize=10&page=1"
                    f"&id={','.join(batch_id_strings)}"
                )

            bgg_response = _http_get_bgg_xml(bg_info_url)
            soup_xml = BeautifulSoup(bgg_response.content, "xml")
            games_xml_list = soup_xml.find_all(
                "item", attrs={"type": ["boardgame", "boardgameexpansion"]}
            )
            if len(games_xml_list) == 0:
                raise RuntimeError(
                    f"BGG API returned zero items for batch URL: {bg_info_url}"
                )

            batch_game_dicts = []
            for game_xml in games_xml_list:
                game_dict = extract_basic_game_info(game_xml=game_xml)
                if not simple_mode:
                    game_dict = extract_polls(game_dict=game_dict, game_xml=game_xml)
                    game_dict = extract_poll_player_count(
                        game_dict=game_dict, game_xml=game_xml
                    )
                    game_dict = extract_version_info(
                        game_dict=game_dict, game_xml=game_xml
                    )
                batch_game_dicts.append(game_dict)

            _upsert_game_batch(conn, batch_game_dicts)
            if batch_saves and (batch_num + 1) % save_every_n_batches == 0:
                logger.info("Checkpointed batch %d to %s", batch_num + 1, save_path)
            sleep(1)

        boardgame_df = _load_game_data_from_store(conn)
        logger.info("Successfully completed fetching all boardgame data")
        logger.info("Saved final data to %s", save_path)
        return boardgame_df
    finally:
        conn.close()
        logger.setLevel(current_level)


def get_boardgame_data(
    boardgame_ranks: pd.DataFrame,
    boardgame_data: pd.DataFrame = None,
    existing_store_path: Path | None = None,
    batch_saves: bool = False,
    batch_size: int = 20,
    save_every_n_batches: int = 1,
    log_level: str = "INFO",
):
    """
    Fetch detailed information for each board game from BGG API.
    The BGG API has a limit of 20 IDs per request, so we process in batches.

    Args:
        boardgame_ranks (pd.DataFrame): DataFrame from get_boardgame_ranks()
        boardgame_data (pd.DataFrame, optional): Existing game data to update
        batch_saves (bool): Whether to save data after each batch
        batch_size (int): Number of games to process in each batch. BGG API has a limit of 20 IDs per request.
        save_every_n_batches (int): Save data after every N batches (default: 1)
        log_level (str): Logging level for this function

    Returns:
        pd.DataFrame: DataFrame containing detailed game information
    """
    return _run_game_data_ingest(
        boardgame_ranks=boardgame_ranks,
        boardgame_data=boardgame_data,
        existing_store_path=existing_store_path,
        batch_saves=batch_saves,
        batch_size=batch_size,
        save_every_n_batches=save_every_n_batches,
        log_level=log_level,
        simple_mode=False,
    )


def extract_basic_game_info(game_xml: bs4.element.Tag):
    """Extract basic game information from BGG XML response."""
    logger.debug(f"Extracting basic game info for {game_xml['id']}")
    game_dict = {
        "id": int(game_xml["id"]),
    }
    if game_xml.find("image") is not None:
        game_dict["thumbnail"] = game_xml.find("thumbnail").text
        game_dict["image"] = game_xml.find("image").text
    game_dict["description"] = game_xml.find("description").text
    values_int = [
        "minplayers",
        "maxplayers",
        "playingtime",
        "minplaytime",
        "maxplaytime",
        "minage",
    ]
    for vals in values_int:
        if game_xml.find(vals) is not None:
            game_dict[vals] = game_xml.find(vals)["value"]
    link_categ = [
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
    for categ in link_categ:
        game_dict[categ] = {
            int(x["id"]): x["value"]
            for x in game_xml.find_all("link", {"type": categ}, recursive=False)
        }
    stats_float = ["stddev", "median", "averageweight"]
    for stat in stats_float:
        if game_xml.find(stat) is not None:
            game_dict[stat] = float(game_xml.find(stat)["value"])
    stats_int = [
        "owned",
        "trading",
        "wanting",
        "wishing",
        "numcomments",
        "numweights",
    ]
    for stat in stats_int:
        if game_xml.find(stat) is not None:
            game_dict[stat] = int(game_xml.find(stat)["value"])
    if game_xml.find("comments") is not None:
        game_dict["numratings"] = int(game_xml.find("comments")["totalitems"])
    else:
        game_dict["numratings"] = 0
    logger.debug(f"Successfully extracted basic game info for {game_xml['id']}")
    return game_dict


def extract_polls(game_dict: dict, game_xml: bs4.element.Tag):
    """Extract poll data from BGG XML."""
    logger.debug(f"Extracting polls for {game_xml['id']}")
    for poll_name in ["suggested_playerage", "language_dependence"]:
        if poll_name == "suggested_playerage":
            raw_value_col = "value"
        elif poll_name == "language_dependence":
            raw_value_col = "level"
        poll = game_xml.find("poll", attrs={"name": poll_name})
        vote_count = int(poll.attrs["totalvotes"])
        if vote_count > 0:
            result_dict = {"total_votes": vote_count}
            cum_votes = 0
            suggested_prcnt = {}
            suggested_prcnt_col = "value"
            for result_val in poll.find("results").find_all("result"):
                num_votes = int(result_val["numvotes"])
                cum_votes += num_votes
                cum_prcnt = round(cum_votes / vote_count * 100)
                result_dict[result_val[raw_value_col]] = num_votes
                sugg_prcnt_val = result_val[suggested_prcnt_col]
                if cum_prcnt >= 75:
                    if "75 percent" not in suggested_prcnt:
                        suggested_prcnt["75 percent"] = sugg_prcnt_val
                    if "50 percent" not in suggested_prcnt:
                        suggested_prcnt["50 percent"] = sugg_prcnt_val
                    if "25 percent" not in suggested_prcnt:
                        suggested_prcnt["25 percent"] = sugg_prcnt_val
                elif cum_prcnt >= 50:
                    suggested_prcnt["50 percent"] = sugg_prcnt_val
                    if "25 percent" not in suggested_prcnt:
                        suggested_prcnt["25 percent"] = sugg_prcnt_val
                elif cum_prcnt >= 25:
                    suggested_prcnt["25 percent"] = sugg_prcnt_val
        else:
            result_dict = {}
            suggested_prcnt = {}
        game_dict[poll_name] = result_dict
        game_dict[f"{poll_name}_quartiles"] = suggested_prcnt
    logger.debug(f"Successfully extracted polls for {game_xml['id']}")
    return game_dict


def extract_poll_player_count(game_dict: dict, game_xml: bs4.element.Tag):
    """Extract player count recommendations from BGG XML."""
    logger.debug(f"Extracting player count poll for {game_xml['id']}")
    player_count_poll = game_xml.find("poll", attrs={"name": "suggested_numplayers"})
    result_dict = {"total_votes": int(player_count_poll.attrs["totalvotes"])}
    if result_dict["total_votes"] == 0:
        game_dict["player_count_recs"] = {}
        game_dict["suggested_numplayers"] = {}
        logger.debug(f"Missing player count poll for {game_xml['id']}")
        return game_dict
    player_count_results = player_count_poll.find_all("results")
    game_dict["player_count_recs"] = {}
    for player_count in player_count_results:
        num_players = player_count.attrs["numplayers"]
        player_count_values = {
            x.attrs["value"]: int(x.attrs["numvotes"])
            for x in player_count.find_all("result")
        }
        play_count_rec = max(player_count_values, key=player_count_values.get)
        if play_count_rec in game_dict["player_count_recs"]:
            game_dict["player_count_recs"][play_count_rec].append(num_players)
        else:
            game_dict["player_count_recs"][play_count_rec] = [num_players]
        result_dict[num_players] = player_count_values
        result_dict[num_players]["total_votes"] = sum(
            int(x.attrs["numvotes"]) for x in player_count.find_all("result")
        )
    game_dict["suggested_numplayers"] = result_dict
    logger.debug(f"Successfully extracted player count poll for {game_xml['id']}")
    return game_dict


def extract_version_info(game_dict: dict, game_xml: bs4.element.Tag):
    """Extract version information from BGG XML."""
    logger.debug(f"Extracting version info for {game_xml['id']}")
    version_items = game_xml.find_all("item", attrs={"type": "boardgameversion"})
    version_list = []
    for vrs in version_items:
        try:
            version_dict = {
                "version_id": int(vrs["id"]),
                "width": round(float(vrs.find("width")["value"])),
                "length": round(float(vrs.find("length")["value"])),
                "depth": round(float(vrs.find("depth")["value"])),
                "year_published": round(float(vrs.find("yearpublished")["value"])),
            }
            if vrs.find("thumbnail") is not None:
                version_dict["thumbnail"] = vrs.find("thumbnail").text
                version_dict["image"] = vrs.find("image").text
            if vrs.find("link", attrs={"type": "language"}) is not None:
                version_dict["language"] = vrs.find("link", attrs={"type": "language"})[
                    "value"
                ].lower()
            if vrs.find("name", attrs={"type": "primary"}) is not None:
                version_dict["version_nickname"] = vrs.find(
                    "name", attrs={"type": "primary"}
                )["value"]
            if version_dict["width"] > 0:
                version_list.append(version_dict)
        except TypeError as e:
            logger.error(
                f"TypeError processing version for game ID {game_xml['id']}: {str(e)}"
            )
            raise
    if len(version_list) > 0:
        game_dict["versions"] = version_list
    logger.debug(f"Successfully extracted version info for {game_xml['id']}")
    return game_dict


def get_simple_game_data(
    boardgame_ranks: pd.DataFrame,
    boardgame_data: pd.DataFrame = None,
    existing_store_path: Path | None = None,
    batch_saves: bool = False,
    batch_size: int = 20,
    save_every_n_batches: int = 1,
    log_level: str = "INFO",
):
    """
    Fetch basic game information for each board game from BGG API using a simplified approach.
    This version uses a simpler API call and skips complex data extraction.

    Args:
        boardgame_ranks (pd.DataFrame): DataFrame from get_boardgame_ranks()
        boardgame_data (pd.DataFrame, optional): Existing game data to update
        batch_saves (bool): Whether to save data after each batch
        batch_size (int): Number of games to process in each batch
        save_every_n_batches (int): Save data after every N batches (default: 1)
        log_level (str): Logging level for this function

    Returns:
        pd.DataFrame: DataFrame containing basic game information
    """
    return _run_game_data_ingest(
        boardgame_ranks=boardgame_ranks,
        boardgame_data=boardgame_data,
        existing_store_path=existing_store_path,
        batch_saves=batch_saves,
        batch_size=batch_size,
        save_every_n_batches=save_every_n_batches,
        log_level=log_level,
        simple_mode=True,
    )


def main():
    """Main function to get board game data."""
    try:
        # Set up argument parser
        parser = argparse.ArgumentParser(description="Get board game data from BGG")
        parser.add_argument(
            "--continue-from-last",
            action="store_true",
            help="Continue from the most recent output file",
        )
        parser.add_argument(
            "--simple",
            action="store_true",
            help="Use simplified data collection (skips complex data extraction)",
        )
        parser.add_argument(
            "--save-every-n-batches",
            type=int,
            default=1,
            help="Save data after every N batches (default: 1)",
        )
        args = parser.parse_args()

        # Get the most recent rankings file
        ranks_dir = Path(__file__).resolve().parents[3] / "data" / "ingest" / "ranks"
        game_data_dir = (
            Path(__file__).resolve().parents[3] / "data" / "ingest" / "game_data"
        )
        ranks_files = list(ranks_dir.glob("boardgame_ranks_*.csv"))
        if not ranks_files:
            raise FileNotFoundError("No rankings files found")

        latest_ranks = max(ranks_files, key=lambda x: x.stat().st_mtime)
        logger.info(f"Using rankings file: {latest_ranks}")

        # Read rankings
        df_ranks = pd.read_csv(
            latest_ranks, sep="|", escapechar="\\", quoting=csv.QUOTE_NONE
        )

        # Get existing DuckDB store if continuing
        existing_store_path = None
        if args.continue_from_last:
            file_pattern = (
                "boardgame_simple_data_*.duckdb"
                if args.simple
                else "boardgame_data_*.duckdb"
            )
            game_files = list(game_data_dir.glob(file_pattern))
            if game_files:
                latest_games = max(game_files, key=lambda x: x.stat().st_mtime)
                logger.info(f"Continuing from game data store: {latest_games}")
                existing_store_path = latest_games

        # Get game data
        if args.simple:
            df_games = get_simple_game_data(
                df_ranks,
                existing_store_path=existing_store_path,
                batch_saves=True,
                save_every_n_batches=args.save_every_n_batches,
            )
        else:
            df_games = get_boardgame_data(
                df_ranks,
                existing_store_path=existing_store_path,
                batch_saves=True,
                save_every_n_batches=args.save_every_n_batches,
            )
        logger.info("Successfully completed getting board game data")
        return df_games

    except Exception as e:
        logger.error(f"Error getting board game data: {str(e)}")
        raise


if __name__ == "__main__":
    main()
