"""
BoardGameGeek (BGG) Rankings Downloader

This script downloads the current board game rankings ZIP from a signed URL.
It is the first step in the data collection pipeline and should be run before
`get_game_data.py`.

Execution order:
1. get_ranks.py - Downloads board game rankings
2. get_game_data.py - Gets detailed game information
3. get_ratings.py - Gets user ratings for each game

How to obtain the signed URL:
1. Log in to BoardGameGeek.
2. Open https://boardgamegeek.com/data_dumps/bg_ranks
3. Copy the current boardgame ranks ZIP link from that page.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from io import BytesIO
import logging
import os
from pathlib import Path
from zipfile import ZipFile

from dotenv import find_dotenv, load_dotenv
import pandas as pd
import requests
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


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=build_log_handlers("get_ranks.log"),
)
logger = logging.getLogger(__name__)

RANKS_CSV_FILENAME = "boardgames_ranks.csv"


def _load_ranks_dataframe(zip_bytes: bytes, queried_at_utc: str) -> pd.DataFrame:
    with ZipFile(BytesIO(zip_bytes)) as archive:
        with archive.open(RANKS_CSV_FILENAME) as csv_file:
            df = pd.read_csv(csv_file)
    df["name"] = df["name"].str.replace("[“”]", '"', regex=True)
    df["queried_at_utc"] = queried_at_utc
    return df


def _save_ranks_dataframe(df_ranks: pd.DataFrame, queried_at_utc: str) -> Path:
    data_dir = Path(__file__).resolve().parents[3] / "data" / "ingest" / "ranks"
    data_dir.mkdir(parents=True, exist_ok=True)
    output_file = (
        data_dir / f"boardgame_ranks_{queried_at_utc[:10].replace('-', '')}.csv"
    )
    df_ranks.to_csv(
        output_file,
        index=False,
        sep="|",
        escapechar="\\",
        quoting=csv.QUOTE_NONE,
    )
    return output_file


@retry(
    retry=retry_if_exception_type(requests.RequestException),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
def _http_get(url: str) -> requests.Response:
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    return response


def get_boardgame_ranks(
    ranks_zip_url: str,
    save_file: bool = False,
) -> pd.DataFrame:
    if not ranks_zip_url.strip():
        raise ValueError("ranks_zip_url is required")

    logger.info("Fetching boardgame ranks from direct signed URL")
    queried_at_utc = datetime.now().replace(microsecond=0).isoformat()
    ranks_zip_response = _http_get(ranks_zip_url.strip())
    df_bg_ranks = _load_ranks_dataframe(ranks_zip_response.content, queried_at_utc)
    logger.info("Successfully loaded %d boardgames", len(df_bg_ranks))

    if save_file:
        output_file = _save_ranks_dataframe(df_bg_ranks, queried_at_utc)
        logger.info("Saved rankings to %s", output_file)
    return df_bg_ranks


def main() -> None:
    parser = argparse.ArgumentParser(description="Get board game rankings from BGG.")
    parser.add_argument(
        "--ranks-zip-url",
        default=None,
        help=(
            "Direct signed boardgame ranks ZIP URL. "
            "Obtain it from https://boardgamegeek.com/data_dumps/bg_ranks "
            "after logging in to BGG."
        ),
    )
    args = parser.parse_args()

    load_dotenv(find_dotenv())
    ranks_zip_url = (args.ranks_zip_url or os.getenv("BGG_RANKS_ZIP_URL") or "").strip()
    if not ranks_zip_url:
        raise ValueError(
            "Missing ranks ZIP URL. Provide --ranks-zip-url or set "
            "BGG_RANKS_ZIP_URL. Get the signed link from "
            "https://boardgamegeek.com/data_dumps/bg_ranks after logging in."
        )

    get_boardgame_ranks(ranks_zip_url=ranks_zip_url, save_file=True)
    logger.info("Successfully completed getting board game rankings")


if __name__ == "__main__":
    main()
