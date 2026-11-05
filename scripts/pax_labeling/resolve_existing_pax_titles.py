#!/usr/bin/env python3

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

import pandas as pd
from rapidfuzz import fuzz, process

from scripts.pax_labeling.matcher import (
    BggFixMap,
    MatchingRules,
    TitleFixMap,
    TitlePriorMap,
    build_first_publisher_index,
    build_title_indexes,
    build_title_prior_map,
    clean_raw_publisher,
    confidence_from_top_candidates,
    load_bgg_data,
    load_excluded_title_ids,
    load_manual_fixes_csv,
    normalize_text,
    rank_candidates,
    score_candidate,
)

logger = logging.getLogger(__name__)


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )


def coerce_optional_int(value: Any) -> int | None:
    if pd.isna(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def resolve_matches(
    raw_df: pd.DataFrame,
    *,
    games_df: pd.DataFrame,
    publishers_by_game: dict[int, set[str]],
    versions_by_game: dict[int, tuple[str, ...]],
    bgg_id_fixes: BggFixMap,
    title_id_fixes: TitleFixMap,
    title_priors: TitlePriorMap,
    excluded_title_ids: set[int],
    fuzzy_limit: int,
    fuzzy_cutoff: int,
    review_margin: float,
    rules: MatchingRules,
    publisher_first_fallback: bool = True,
    publisher_first_max_candidates: int = 250,
    publisher_first_title_score_threshold: float = 94.0,
    publisher_first_margin_threshold: float = 50.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    ids_by_title_norm, ids_by_title_key, fuzzy_by_first_char, fuzzy_titles = (
        build_title_indexes(games_df)
    )
    first_publisher_index = build_first_publisher_index(games_df)
    games_lookup = games_df.set_index("id").to_dict("index")

    work_df = raw_df.copy()
    work_df["title_norm"] = work_df["title"].map(normalize_text)
    work_df["title_key"] = work_df["title"].map(
        lambda value: normalize_text(value, alnum_only=True)
    )
    work_df["publisher_norm"] = work_df["publisher_name"].map(clean_raw_publisher)
    work_df["game_year_num"] = pd.to_numeric(
        work_df["game_year"], errors="coerce"
    ).astype("Int64")
    work_df["bgg_id_num"] = pd.to_numeric(work_df["bgg_id"], errors="coerce").astype(
        "Int64"
    )

    resolved_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []

    for row in work_df.itertuples(index=False):
        row_dict = row._asdict()
        title_id = coerce_optional_int(row_dict.get("title_id"))
        row_bgg_id = coerce_optional_int(row_dict.get("bgg_id_num"))
        row_game_year = coerce_optional_int(row_dict.get("game_year_num"))
        row_title_norm = str(row_dict.get("title_norm", ""))
        row_title_key = str(row_dict.get("title_key", ""))
        row_publisher_norm = str(row_dict.get("publisher_norm", ""))
        is_excluded_title_id = title_id is not None and title_id in excluded_title_ids

        original_bgg_name = (
            str(games_lookup[row_bgg_id]["name"])
            if row_bgg_id is not None and row_bgg_id in games_lookup
            else None
        )

        if is_excluded_title_id:
            resolved_rows.append(
                {
                    "original_bgg_name": original_bgg_name,
                    "new_bgg_id": None,
                    "new_bgg_name": None,
                    "match_confidence": "excluded",
                    "match_reason": "excluded_title_id_list",
                    "match_score_margin": None,
                    "top_candidate_count": 0,
                    "excluded_title_id": True,
                    "used_publisher_first_fallback": False,
                }
            )
            continue

        forced_title_fix = (
            title_id_fixes.get(title_id) if title_id is not None else None
        )
        forced_bgg_fix = (
            bgg_id_fixes.get(row_bgg_id) if row_bgg_id is not None else None
        )

        candidate_ids: set[int] = set()
        if forced_title_fix is not None:
            candidate_ids.add(int(forced_title_fix))
        if forced_bgg_fix is not None:
            candidate_ids.add(int(forced_bgg_fix))
        if row_bgg_id is not None:
            candidate_ids.add(row_bgg_id)

        priors_for_title = (
            title_priors.get(title_id, set()) if title_id is not None else set()
        )
        candidate_ids.update(priors_for_title)

        candidate_ids.update(ids_by_title_norm.get(row_title_norm, set()))
        candidate_ids.update(ids_by_title_key.get(row_title_key, set()))

        if row_title_norm:
            first_char = row_title_norm[0]
            fuzzy_pool = list(fuzzy_by_first_char.get(first_char, set()))
            if not fuzzy_pool:
                fuzzy_pool = fuzzy_titles
            fuzzy_matches = process.extract(
                row_title_norm,
                fuzzy_pool,
                scorer=fuzz.WRatio,
                limit=fuzzy_limit,
                score_cutoff=fuzzy_cutoff,
            )
            for match in fuzzy_matches:
                matched_title = str(match[0])
                candidate_ids.update(ids_by_title_norm.get(matched_title, set()))

        candidate_ids = {
            candidate_id
            for candidate_id in candidate_ids
            if candidate_id in games_lookup
        }

        scored_candidates = [
            score_candidate(
                candidate_id=candidate_id,
                row_title_norm=row_title_norm,
                row_title_key=row_title_key,
                row_publisher_norm=row_publisher_norm,
                row_game_year=row_game_year,
                row_bgg_id=row_bgg_id,
                games_lookup=games_lookup,
                publishers_by_game=publishers_by_game,
                versions_by_game=versions_by_game,
                title_priors=priors_for_title,
                forced_title_fix=forced_title_fix,
                forced_bgg_fix=forced_bgg_fix,
                rules=rules,
            )
            for candidate_id in candidate_ids
        ]
        scored_candidates = rank_candidates(scored_candidates)

        used_publisher_first_fallback = False
        publisher_fallback_added: set[int] = set()

        base_top1 = scored_candidates[0] if scored_candidates else None
        base_top2 = scored_candidates[1] if len(scored_candidates) > 1 else None
        base_margin = (
            (base_top1.score - base_top2.score)
            if base_top1 is not None and base_top2 is not None
            else (9999.0 if base_top1 is not None else None)
        )

        should_apply_publisher_first = (
            publisher_first_fallback
            and bool(row_publisher_norm)
            and forced_title_fix is None
            and forced_bgg_fix is None
        )
        if should_apply_publisher_first:
            weak_or_ambiguous = (
                base_top1 is None
                or base_top1.title_score < publisher_first_title_score_threshold
                or (
                    base_margin is not None
                    and base_margin < publisher_first_margin_threshold
                )
            )
            if weak_or_ambiguous:
                publisher_candidates = first_publisher_index.get(row_publisher_norm, [])
                if publisher_candidates:
                    for publisher_candidate_id in publisher_candidates:
                        if publisher_candidate_id in candidate_ids:
                            continue
                        candidate_year_raw = games_lookup[publisher_candidate_id].get(
                            "yearpublished"
                        )
                        candidate_year = (
                            int(candidate_year_raw)
                            if pd.notna(candidate_year_raw)
                            else None
                        )
                        if (
                            row_game_year is not None
                            and candidate_year is not None
                            and row_game_year + 1 < candidate_year
                        ):
                            continue
                        candidate_ids.add(publisher_candidate_id)
                        publisher_fallback_added.add(publisher_candidate_id)
                        if (
                            len(publisher_fallback_added)
                            >= publisher_first_max_candidates
                        ):
                            break

        if publisher_fallback_added:
            used_publisher_first_fallback = True
            scored_candidates = [
                score_candidate(
                    candidate_id=candidate_id,
                    row_title_norm=row_title_norm,
                    row_title_key=row_title_key,
                    row_publisher_norm=row_publisher_norm,
                    row_game_year=row_game_year,
                    row_bgg_id=row_bgg_id,
                    games_lookup=games_lookup,
                    publishers_by_game=publishers_by_game,
                    versions_by_game=versions_by_game,
                    title_priors=priors_for_title,
                    forced_title_fix=forced_title_fix,
                    forced_bgg_fix=forced_bgg_fix,
                    rules=rules,
                )
                for candidate_id in candidate_ids
            ]
            scored_candidates = rank_candidates(scored_candidates)

        top_candidates = scored_candidates[:3]
        top1 = top_candidates[0] if top_candidates else None
        top2 = top_candidates[1] if len(top_candidates) > 1 else None

        if forced_title_fix is not None:
            forced_reason = "manual_title_fix"
        elif forced_bgg_fix is not None:
            forced_reason = "manual_bgg_fix"
        else:
            forced_reason = None

        if top1 is not None:
            confidence = confidence_from_top_candidates(
                top1, top2, forced_reason=forced_reason
            )
            new_bgg_id = top1.bgg_id
            new_bgg_name = top1.bgg_name
            if forced_reason is not None:
                match_reason = forced_reason
            elif (
                used_publisher_first_fallback
                and top1.bgg_id in publisher_fallback_added
            ):
                match_reason = "publisher_first_fallback"
            else:
                match_reason = "scored_candidate"
            margin = top1.score - top2.score if top2 is not None else 9999.0
            needs_review = (
                confidence in {"low", "unresolved"}
                or margin < review_margin
                or (
                    row_bgg_id is not None
                    and row_bgg_id != new_bgg_id
                    and forced_reason is None
                )
            )
        else:
            confidence = "unresolved"
            new_bgg_id = None
            new_bgg_name = None
            match_reason = "no_candidate"
            margin = None
            needs_review = True

        resolved_row = {
            "original_bgg_name": original_bgg_name,
            "new_bgg_id": new_bgg_id,
            "new_bgg_name": new_bgg_name,
            "match_confidence": confidence,
            "match_reason": match_reason,
            "match_score_margin": margin,
            "top_candidate_count": len(scored_candidates),
            "excluded_title_id": False,
            "used_publisher_first_fallback": used_publisher_first_fallback,
        }
        resolved_rows.append(resolved_row)

        if needs_review:
            review_row = {
                "title_id": title_id,
                "game_id": row_dict.get("game"),
                "game_barcode": row_dict.get("game_barcode"),
                "title": row_dict.get("title"),
                "publisher_name": row_dict.get("publisher_name"),
                "game_year": row_dict.get("game_year"),
                "original_bgg_id": row_bgg_id,
                "new_bgg_id": new_bgg_id,
                "match_confidence": confidence,
                "match_reason": match_reason,
                "match_score_margin": margin,
            }
            for index in range(3):
                prefix = f"candidate_{index + 1}"
                candidate = (
                    top_candidates[index] if index < len(top_candidates) else None
                )
                if candidate is None:
                    review_row[f"{prefix}_id"] = None
                    review_row[f"{prefix}_name"] = None
                    review_row[f"{prefix}_score"] = None
                    review_row[f"{prefix}_dimensions"] = None
                    review_row[f"{prefix}_title_score"] = None
                    review_row[f"{prefix}_publisher_match_type"] = None
                    review_row[f"{prefix}_year_match"] = None
                    review_row[f"{prefix}_id_match"] = None
                    review_row[f"{prefix}_pax_prior"] = None
                else:
                    review_row[f"{prefix}_id"] = candidate.bgg_id
                    review_row[f"{prefix}_name"] = candidate.bgg_name
                    review_row[f"{prefix}_score"] = round(candidate.score, 3)
                    review_row[f"{prefix}_dimensions"] = candidate.dimension_count
                    review_row[f"{prefix}_title_score"] = round(
                        candidate.title_score, 3
                    )
                    review_row[f"{prefix}_publisher_match_type"] = (
                        candidate.publisher_match_type
                    )
                    review_row[f"{prefix}_year_match"] = candidate.year_match
                    review_row[f"{prefix}_id_match"] = candidate.id_match
                    review_row[f"{prefix}_pax_prior"] = candidate.pax_prior
                    review_row[f"{prefix}_is_expansion"] = candidate.is_expansion
                    review_row[f"{prefix}_has_promo_word"] = candidate.has_promo_word
                    review_row[f"{prefix}_from_publisher_first_fallback"] = (
                        candidate.bgg_id in publisher_fallback_added
                    )
            review_rows.append(review_row)

    result_df = pd.concat(
        [raw_df.reset_index(drop=True), pd.DataFrame(resolved_rows)], axis=1
    )
    review_df = pd.DataFrame(review_rows)
    return result_df, review_df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve existing PAX title rows to BGG ids using title/publisher/year/existing-id "
            "evidence, manual CSV fixes, and prior mappings."
        )
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Input CSV path with existing-title correction rows.",
    )
    parser.add_argument(
        "--input-sep",
        default="|",
        help="Input delimiter (default: pipe).",
    )
    parser.add_argument(
        "--input-encoding",
        default="cp1252",
        help="Input text encoding (default: cp1252).",
    )
    parser.add_argument(
        "--ranks",
        required=True,
        help="BGG ranks CSV path.",
    )
    parser.add_argument(
        "--first-publishers",
        required=True,
        help="First publisher CSV path.",
    )
    parser.add_argument(
        "--all-publishers",
        required=True,
        help="All publisher CSV path.",
    )
    parser.add_argument(
        "--versions",
        required=True,
        help="Versions CSV path.",
    )
    parser.add_argument(
        "--prior-map",
        default=None,
        help="Prior mapping CSV path with min_titles_id -> bgg_id.",
    )
    parser.add_argument(
        "--excluded-title-ids",
        default=None,
        help=(
            "CSV containing title_ids that should be excluded from matching "
            "(expects a title_id column, or first column as ids)."
        ),
    )
    parser.add_argument(
        "--manual-fixes",
        default=None,
        help=(
            "CSV containing manual fix assignments. Supports title_id/min_titles_id -> "
            "bgg_id/new_bgg_id and optional old_bgg_id -> bgg_id/new_bgg_id."
        ),
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output CSV path (same rows/columns as input plus matcher columns).",
    )
    parser.add_argument(
        "--review-output",
        required=True,
        help="Review queue CSV path with top-3 candidate details.",
    )
    parser.add_argument(
        "--fuzzy-limit",
        type=int,
        default=25,
        help="Max fuzzy title candidates to pull per row.",
    )
    parser.add_argument(
        "--fuzzy-cutoff",
        type=int,
        default=84,
        help="Minimum fuzzy title score to keep candidate titles.",
    )
    parser.add_argument(
        "--review-margin",
        type=float,
        default=75.0,
        help="Top-1 vs top-2 score margin below which row is sent to review queue.",
    )
    parser.add_argument(
        "--year-gap-penalty",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Apply penalties for large absolute year gaps between row game_year and candidate yearpublished.",
    )
    parser.add_argument(
        "--year-gap-soft-threshold",
        type=int,
        default=5,
        help="Absolute year-gap threshold for soft penalty (used with --year-gap-penalty).",
    )
    parser.add_argument(
        "--year-gap-hard-threshold",
        type=int,
        default=15,
        help="Absolute year-gap threshold for hard penalty (used with --year-gap-penalty).",
    )
    parser.add_argument(
        "--year-gap-soft-penalty",
        type=float,
        default=250.0,
        help="Score penalty when year gap exceeds soft threshold.",
    )
    parser.add_argument(
        "--year-gap-hard-penalty",
        type=float,
        default=900.0,
        help="Score penalty when year gap exceeds hard threshold.",
    )
    parser.add_argument(
        "--subtitle-penalty",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Penalize candidates that miss subtitle tokens when the row title contains a subtitle "
            "(e.g., text after ':')."
        ),
    )
    parser.add_argument(
        "--subtitle-miss-penalty",
        type=float,
        default=600.0,
        help="Score penalty for subtitle-token miss (used with --subtitle-penalty).",
    )
    parser.add_argument(
        "--publisher-suffix-normalization",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Normalize publisher suffixes (games, inc, llc, etc.) before exact publisher comparisons."
        ),
    )
    parser.add_argument(
        "--generic-title-guard",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Apply extra penalties for generic short titles when publisher/year support is weak."
        ),
    )
    parser.add_argument(
        "--generic-title-max-tokens",
        type=int,
        default=1,
        help="Title is considered generic if token count is <= this value.",
    )
    parser.add_argument(
        "--generic-title-max-length",
        type=int,
        default=10,
        help="Title is considered generic if alnum length is <= this value.",
    )
    parser.add_argument(
        "--generic-title-without-publisher-penalty",
        type=float,
        default=450.0,
        help="Penalty applied when generic-title guard is on and publisher does not match.",
    )
    parser.add_argument(
        "--generic-title-without-year-penalty",
        type=float,
        default=200.0,
        help="Penalty applied when generic-title guard is on and year does not match.",
    )
    parser.add_argument(
        "--popularity-override",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "When enabled, high-popularity strong-title matches can bypass year-gap and "
            "generic-title penalties."
        ),
    )
    parser.add_argument(
        "--popularity-override-min-usersrated",
        type=int,
        default=3000,
        help="Minimum usersrated for popularity override.",
    )
    parser.add_argument(
        "--popularity-override-min-title-score",
        type=float,
        default=95.0,
        help="Minimum title score for popularity override.",
    )
    parser.add_argument(
        "--publisher-first-fallback",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Enable fallback candidate expansion by exact first_publisher match "
            "when title-led matching is weak or ambiguous."
        ),
    )
    parser.add_argument(
        "--publisher-first-max-candidates",
        type=int,
        default=250,
        help="Maximum first_publisher fallback candidates added per row.",
    )
    parser.add_argument(
        "--publisher-first-title-score-threshold",
        type=float,
        default=94.0,
        help=(
            "If top title score is below this threshold, publisher-first fallback can trigger."
        ),
    )
    parser.add_argument(
        "--publisher-first-margin-threshold",
        type=float,
        default=50.0,
        help=(
            "If top-vs-second score margin is below this threshold, publisher-first fallback can trigger."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging(args.verbose)

    input_path = Path(args.input)
    output_path = Path(args.output)
    review_output_path = Path(args.review_output)

    raw_df = pd.read_csv(
        input_path,
        sep=args.input_sep,
        encoding=args.input_encoding,
    )
    logger.info("Loaded raw input: %s rows from %s", len(raw_df), input_path)

    if args.manual_fixes:
        bgg_id_fixes, title_id_fixes = load_manual_fixes_csv(Path(args.manual_fixes))
    else:
        bgg_id_fixes, title_id_fixes = {}, {}
    title_priors = build_title_prior_map(Path(args.prior_map)) if args.prior_map else {}
    excluded_title_ids = (
        load_excluded_title_ids(Path(args.excluded_title_ids))
        if args.excluded_title_ids
        else set()
    )
    rules = MatchingRules(
        year_gap_penalty_enabled=args.year_gap_penalty,
        year_gap_soft_threshold=args.year_gap_soft_threshold,
        year_gap_hard_threshold=args.year_gap_hard_threshold,
        year_gap_soft_penalty=args.year_gap_soft_penalty,
        year_gap_hard_penalty=args.year_gap_hard_penalty,
        subtitle_penalty_enabled=args.subtitle_penalty,
        subtitle_miss_penalty=args.subtitle_miss_penalty,
        publisher_suffix_normalization_enabled=args.publisher_suffix_normalization,
        generic_title_guard_enabled=args.generic_title_guard,
        generic_title_max_tokens=args.generic_title_max_tokens,
        generic_title_max_length=args.generic_title_max_length,
        generic_title_without_publisher_penalty=args.generic_title_without_publisher_penalty,
        generic_title_without_year_penalty=args.generic_title_without_year_penalty,
        popularity_override_enabled=args.popularity_override,
        popularity_override_min_usersrated=args.popularity_override_min_usersrated,
        popularity_override_min_title_score=args.popularity_override_min_title_score,
    )
    games_df, publishers_by_game, versions_by_game = load_bgg_data(
        Path(args.ranks),
        Path(args.first_publishers),
        Path(args.all_publishers),
        Path(args.versions),
    )

    result_df, review_df = resolve_matches(
        raw_df=raw_df,
        games_df=games_df,
        publishers_by_game=publishers_by_game,
        versions_by_game=versions_by_game,
        bgg_id_fixes=bgg_id_fixes,
        title_id_fixes=title_id_fixes,
        title_priors=title_priors,
        excluded_title_ids=excluded_title_ids,
        fuzzy_limit=args.fuzzy_limit,
        fuzzy_cutoff=args.fuzzy_cutoff,
        review_margin=args.review_margin,
        rules=rules,
        publisher_first_fallback=args.publisher_first_fallback,
        publisher_first_max_candidates=args.publisher_first_max_candidates,
        publisher_first_title_score_threshold=args.publisher_first_title_score_threshold,
        publisher_first_margin_threshold=args.publisher_first_margin_threshold,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    review_output_path.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(output_path, index=False, encoding="utf-8")
    review_df.to_csv(review_output_path, index=False, encoding="utf-8")

    logger.info("Wrote resolved output: %s rows to %s", len(result_df), output_path)
    logger.info("Wrote review queue: %s rows to %s", len(review_df), review_output_path)

    if "new_bgg_id" in result_df.columns:
        changed_count = int(
            (
                pd.to_numeric(result_df["bgg_id"], errors="coerce")
                != pd.to_numeric(result_df["new_bgg_id"], errors="coerce")
            )
            .fillna(False)
            .sum()
        )
        logger.info(
            "Rows where new_bgg_id differs from original bgg_id: %s", changed_count
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
