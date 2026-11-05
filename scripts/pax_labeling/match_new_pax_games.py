#!/usr/bin/env python3

from __future__ import annotations

import argparse
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
from rapidfuzz import fuzz, process

from scripts.pax_labeling.matcher import (
    MatchingRules,
    build_first_publisher_index,
    build_title_indexes,
    clean_raw_publisher,
    load_bgg_data,
    normalize_text,
    rank_candidates,
    score_candidate,
)


logger = logging.getLogger(__name__)

OUTPUT_COLUMNS = [
    "title",
    "publisher_name",
    "bgg_id",
    "bgg_name",
    "bgg_publishers",
    "year_published",
]


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )


def load_input_csv(path: Path, *, sep: str, encoding: str) -> pd.DataFrame:
    frame = pd.read_csv(path, sep=sep, encoding=encoding)
    missing = {"title", "publisher_name"} - set(frame.columns)
    if missing:
        missing_cols = ", ".join(sorted(missing))
        raise ValueError(
            f"Input CSV is missing required columns: {missing_cols}. "
            "Expected at least: title, publisher_name."
        )
    return frame


def load_bgg_publisher_display_map(
    *,
    first_publishers_path: Path,
    all_publishers_path: Path,
) -> dict[int, tuple[str, ...]]:
    publisher_map: dict[int, list[str]] = defaultdict(list)

    first_df = pd.read_csv(first_publishers_path)
    first_df = first_df.rename(columns={"id": "game_id", "publisher": "publisher_name"})
    first_df["game_id"] = pd.to_numeric(first_df["game_id"], errors="coerce")
    first_df = first_df.dropna(subset=["game_id"])
    for row in first_df.itertuples(index=False):
        game_id = int(row.game_id)
        publisher_name = str(getattr(row, "publisher_name", "") or "").strip()
        if publisher_name:
            publisher_map[game_id].append(publisher_name)

    all_df = pd.read_csv(
        all_publishers_path,
        sep="|",
        usecols=["game_id", "boardgamepublisher_name"],
        low_memory=False,
    )
    all_df["game_id"] = pd.to_numeric(all_df["game_id"], errors="coerce")
    all_df = all_df.dropna(subset=["game_id"])
    for row in all_df.itertuples(index=False):
        game_id = int(row.game_id)
        publisher_name = str(getattr(row, "boardgamepublisher_name", "") or "").strip()
        if publisher_name:
            publisher_map[game_id].append(publisher_name)

    deduped_map: dict[int, tuple[str, ...]] = {}
    for game_id, publishers in publisher_map.items():
        unique_publishers = tuple(dict.fromkeys(publishers))
        deduped_map[game_id] = unique_publishers
    return deduped_map


def build_best_matches(
    input_df: pd.DataFrame,
    *,
    games_df: pd.DataFrame,
    publishers_by_game: dict[int, set[str]],
    versions_by_game: dict[int, tuple[str, ...]],
    publishers_display_by_game: dict[int, tuple[str, ...]],
    fuzzy_limit: int,
    fuzzy_cutoff: int,
    publisher_first_max_candidates: int,
) -> pd.DataFrame:
    missing = {"title", "publisher_name"} - set(input_df.columns)
    if missing:
        missing_cols = ", ".join(sorted(missing))
        raise ValueError(f"Input dataframe is missing required columns: {missing_cols}")

    ids_by_title_norm, ids_by_title_key, fuzzy_by_first_char, fuzzy_titles = (
        build_title_indexes(games_df)
    )
    first_publisher_index = build_first_publisher_index(games_df)
    games_lookup = games_df.set_index("id").to_dict("index")
    rules = MatchingRules()

    output_rows: list[dict[str, Any]] = []

    for row in input_df.itertuples(index=False):
        row_dict = row._asdict()
        raw_title = row_dict.get("title")
        raw_publisher = row_dict.get("publisher_name")
        row_title_norm = normalize_text(raw_title)
        row_title_key = normalize_text(raw_title, alnum_only=True)
        row_publisher_norm = clean_raw_publisher(raw_publisher)

        candidate_ids: set[int] = set()
        candidate_ids.update(ids_by_title_norm.get(row_title_norm, set()))
        candidate_ids.update(ids_by_title_key.get(row_title_key, set()))

        if row_title_norm:
            first_char = row_title_norm[0]
            fuzzy_pool = (
                list(fuzzy_by_first_char.get(first_char, set())) or fuzzy_titles
            )
            fuzzy_matches = process.extract(
                row_title_norm,
                fuzzy_pool,
                scorer=fuzz.WRatio,
                limit=fuzzy_limit,
                score_cutoff=fuzzy_cutoff,
            )
            for fuzzy_match in fuzzy_matches:
                fuzzy_title = str(fuzzy_match[0])
                candidate_ids.update(ids_by_title_norm.get(fuzzy_title, set()))

        if row_publisher_norm:
            fallback_ids = first_publisher_index.get(row_publisher_norm, [])
            candidate_ids.update(fallback_ids[:publisher_first_max_candidates])

        scored_candidates = [
            score_candidate(
                candidate_id=candidate_id,
                row_title_norm=row_title_norm,
                row_title_key=row_title_key,
                row_publisher_norm=row_publisher_norm,
                row_game_year=None,
                row_bgg_id=None,
                games_lookup=games_lookup,
                publishers_by_game=publishers_by_game,
                versions_by_game=versions_by_game,
                title_priors=set(),
                forced_title_fix=None,
                forced_bgg_fix=None,
                rules=rules,
            )
            for candidate_id in candidate_ids
            if candidate_id in games_lookup
        ]
        scored_candidates = rank_candidates(scored_candidates)

        top = scored_candidates[0] if scored_candidates else None
        if top is None:
            output_rows.append(
                {
                    "title": raw_title,
                    "publisher_name": raw_publisher,
                    "bgg_id": pd.NA,
                    "bgg_name": pd.NA,
                    "bgg_publishers": pd.NA,
                    "year_published": pd.NA,
                }
            )
            continue

        game = games_lookup[top.bgg_id]
        year_raw = game.get("yearpublished")
        year_published = int(year_raw) if pd.notna(year_raw) else pd.NA
        display_publishers = publishers_display_by_game.get(top.bgg_id, tuple())
        output_rows.append(
            {
                "title": raw_title,
                "publisher_name": raw_publisher,
                "bgg_id": int(top.bgg_id),
                "bgg_name": top.bgg_name,
                "bgg_publishers": " | ".join(display_publishers)
                if display_publishers
                else pd.NA,
                "year_published": year_published,
            }
        )

    return pd.DataFrame(output_rows, columns=OUTPUT_COLUMNS)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Match new PAX game rows containing title/publisher_name to BGG records."
        )
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Input CSV path containing title and publisher_name columns.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output CSV path.",
    )
    parser.add_argument(
        "--ranks",
        required=True,
        help="BGG ranks CSV path.",
    )
    parser.add_argument(
        "--first-publishers",
        required=True,
        help="First publishers CSV path.",
    )
    parser.add_argument(
        "--all-publishers",
        required=True,
        help="All publishers CSV path.",
    )
    parser.add_argument(
        "--versions",
        required=True,
        help="Versions CSV path.",
    )
    parser.add_argument(
        "--input-sep",
        default=",",
        help="Input delimiter (default: comma).",
    )
    parser.add_argument(
        "--input-encoding",
        default="utf-8",
        help="Input text encoding (default: utf-8).",
    )
    parser.add_argument(
        "--fuzzy-limit",
        type=int,
        default=25,
        help="Max fuzzy-title candidate titles evaluated per row.",
    )
    parser.add_argument(
        "--fuzzy-cutoff",
        type=int,
        default=84,
        help="Minimum fuzzy-title score to include candidates.",
    )
    parser.add_argument(
        "--publisher-first-max-candidates",
        type=int,
        default=250,
        help="Maximum additional candidates by exact first-publisher match.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logs.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging(args.verbose)

    input_path = Path(args.input)
    output_path = Path(args.output)

    input_df = load_input_csv(
        input_path,
        sep=args.input_sep,
        encoding=args.input_encoding,
    )
    logger.info("Loaded input rows: %s from %s", len(input_df), input_path)

    games_df, publishers_by_game, versions_by_game = load_bgg_data(
        Path(args.ranks),
        Path(args.first_publishers),
        Path(args.all_publishers),
        Path(args.versions),
    )
    publishers_display_by_game = load_bgg_publisher_display_map(
        first_publishers_path=Path(args.first_publishers),
        all_publishers_path=Path(args.all_publishers),
    )

    matched_df = build_best_matches(
        input_df,
        games_df=games_df,
        publishers_by_game=publishers_by_game,
        versions_by_game=versions_by_game,
        publishers_display_by_game=publishers_display_by_game,
        fuzzy_limit=args.fuzzy_limit,
        fuzzy_cutoff=args.fuzzy_cutoff,
        publisher_first_max_candidates=args.publisher_first_max_candidates,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    matched_df.to_csv(output_path, index=False)
    logger.info("Wrote matched output: %s rows to %s", len(matched_df), output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
