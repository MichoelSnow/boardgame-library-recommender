#!/usr/bin/env python3

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
from rapidfuzz import fuzz

from scripts.pax_labeling.matcher import normalize_text


logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {
    "title",
    "title_id",
    "game",
    "game_barcode",
    "bgg_id",
    "new_bgg_id",
    "new_bgg_name",
    "match_confidence",
    "status",
}

OUTPUT_COLUMNS = [
    "title",
    "title_id",
    "game",
    "game_barcode",
    "bgg_id",
    "match",
    "has_updated_title",
    "title_original",
    "has_updated_bgg_id",
    "bgg_id_original",
]


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def similarity_function(metric: str) -> Callable[[str, str], float]:
    metric_key = metric.casefold()
    if metric_key == "token_sort":
        return fuzz.token_sort_ratio
    if metric_key == "token_set":
        return fuzz.token_set_ratio
    if metric_key == "ratio":
        return fuzz.ratio
    if metric_key == "wratio":
        return fuzz.WRatio
    raise ValueError(f"Unsupported title similarity metric: {metric}")


def require_columns(frame: pd.DataFrame, required_columns: set[str]) -> None:
    missing = sorted(required_columns - set(frame.columns))
    if missing:
        raise ValueError(f"Input CSV missing required columns: {', '.join(missing)}")


def parse_bgg_ids(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def id_changed(old_value: Any, new_value: Any) -> bool:
    if pd.isna(old_value) and pd.isna(new_value):
        return False
    if pd.isna(old_value) != pd.isna(new_value):
        return True
    return int(old_value) != int(new_value)


def load_manual_title_fixes(csv_path: Path) -> dict[int, int]:
    if not csv_path.exists():
        logger.info("Manual fixes file not found at %s; skipping.", csv_path)
        return {}

    fixes_df = pd.read_csv(csv_path, skipinitialspace=True)
    fixes_df.columns = [str(column).strip().casefold() for column in fixes_df.columns]

    target_bgg_col = "new_bgg_id" if "new_bgg_id" in fixes_df.columns else "bgg_id"
    if target_bgg_col not in fixes_df.columns:
        logger.warning(
            "Manual fixes CSV at %s missing bgg_id/new_bgg_id; skipping.",
            csv_path,
        )
        return {}

    title_col = "title_id" if "title_id" in fixes_df.columns else None
    if title_col is None and "min_titles_id" in fixes_df.columns:
        title_col = "min_titles_id"
    if title_col is None:
        logger.warning(
            "Manual fixes CSV at %s missing title_id/min_titles_id; skipping.",
            csv_path,
        )
        return {}

    title_series = pd.to_numeric(fixes_df[title_col], errors="coerce")
    bgg_series = pd.to_numeric(fixes_df[target_bgg_col], errors="coerce")
    valid = title_series.notna() & bgg_series.notna()

    fixes: dict[int, int] = {}
    for title_id, bgg_id in zip(title_series[valid], bgg_series[valid], strict=False):
        fixes[int(title_id)] = int(bgg_id)

    logger.info("Loaded %s title_id manual fixes from %s", len(fixes), csv_path)
    return fixes


def load_title_id_set(csv_path: Path) -> set[int]:
    if not csv_path.exists():
        logger.info("Keep-name list not found at %s; skipping.", csv_path)
        return set()

    keep_df = pd.read_csv(csv_path, comment="#")
    if keep_df.empty:
        logger.info("Keep-name list at %s is empty.", csv_path)
        return set()

    if "title_id" in keep_df.columns:
        title_ids = keep_df["title_id"]
    else:
        title_ids = keep_df.iloc[:, 0]

    keep_title_ids = {
        int(value)
        for value in pd.to_numeric(title_ids, errors="coerce").dropna().astype("int64")
    }
    logger.info("Loaded %s keep-name title_ids from %s", len(keep_title_ids), csv_path)
    return keep_title_ids


def load_bgg_name_lookup(ranks_csv_path: Path) -> dict[int, str]:
    if not ranks_csv_path.exists():
        logger.warning(
            "Ranks CSV not found at %s; skipping name lookup.", ranks_csv_path
        )
        return {}

    ranks_df = pd.read_csv(
        ranks_csv_path,
        sep="|",
        escapechar="\\",
        usecols=["id", "name"],
        low_memory=False,
    )
    ranks_df["id"] = pd.to_numeric(ranks_df["id"], errors="coerce")
    ranks_df = ranks_df.dropna(subset=["id"])
    ranks_df["id"] = ranks_df["id"].astype("int64")
    ranks_df["name"] = ranks_df["name"].fillna("").astype(str)

    lookup = {
        int(row.id): row.name for row in ranks_df.itertuples(index=False) if row.name
    }
    logger.info("Loaded %s BGG names from %s", len(lookup), ranks_csv_path)
    return lookup


def build_cleaned_dataframe(
    source_df: pd.DataFrame,
    *,
    title_match_threshold: float,
    title_similarity_metric: str,
    manual_title_fixes: dict[int, int] | None = None,
    keep_name_title_ids: set[int] | None = None,
    bgg_name_lookup: dict[int, str] | None = None,
) -> tuple[pd.DataFrame, pd.Series]:
    require_columns(source_df, REQUIRED_COLUMNS)

    similarity_fn = similarity_function(title_similarity_metric)
    manual_title_fixes = manual_title_fixes or {}
    keep_name_title_ids = keep_name_title_ids or set()
    bgg_name_lookup = bgg_name_lookup or {}

    output_df = source_df.copy()
    output_df["title_original"] = output_df["title"]
    output_df["bgg_id_original"] = parse_bgg_ids(output_df["bgg_id"])
    title_id_num = pd.to_numeric(output_df["title_id"], errors="coerce").astype("Int64")

    match_confidence = (
        output_df["match_confidence"].astype(str).str.strip().str.casefold()
    )
    status_num = pd.to_numeric(output_df["status"], errors="coerce")
    manual_fix_ids = title_id_num.map(
        lambda value: (manual_title_fixes.get(int(value)) if pd.notna(value) else pd.NA)
    ).astype("Int64")
    manual_override_mask = manual_fix_ids.notna()

    eligible_for_bgg_update = (
        match_confidence.eq("high") | status_num.eq(0) | manual_override_mask
    )

    new_bgg_ids = parse_bgg_ids(output_df["new_bgg_id"])
    effective_new_bgg_ids = new_bgg_ids.copy()
    effective_new_bgg_ids.loc[manual_override_mask] = manual_fix_ids.loc[
        manual_override_mask
    ]

    effective_new_bgg_names = output_df["new_bgg_name"].copy()
    for index in output_df.index[manual_override_mask]:
        manual_bgg_id = int(effective_new_bgg_ids.loc[index])
        manual_bgg_name = bgg_name_lookup.get(manual_bgg_id)
        if manual_bgg_name:
            effective_new_bgg_names.loc[index] = manual_bgg_name

    cleaned_bgg_ids = output_df["bgg_id_original"].copy()
    apply_new_bgg_ids = eligible_for_bgg_update & effective_new_bgg_ids.notna()
    cleaned_bgg_ids.loc[apply_new_bgg_ids] = effective_new_bgg_ids.loc[
        apply_new_bgg_ids
    ]
    output_df["bgg_id"] = cleaned_bgg_ids

    title_similarity = pd.Series(np.nan, index=output_df.index, dtype="float64")
    eligible_for_title_update = apply_new_bgg_ids & effective_new_bgg_names.notna()
    if eligible_for_title_update.any():
        scores = [
            float(similarity_fn(normalize_text(old), normalize_text(new)))
            for old, new in zip(
                output_df.loc[eligible_for_title_update, "title_original"],
                effective_new_bgg_names.loc[eligible_for_title_update],
                strict=False,
            )
        ]
        title_similarity.loc[eligible_for_title_update] = scores

    cleaned_titles = output_df["title_original"].copy()
    keep_original_name_mask = title_id_num.map(
        lambda value: int(value) in keep_name_title_ids if pd.notna(value) else False
    )
    apply_new_titles = (
        eligible_for_title_update
        & title_similarity.ge(title_match_threshold)
        & ~keep_original_name_mask
    )
    cleaned_titles.loc[apply_new_titles] = effective_new_bgg_names.loc[apply_new_titles]
    output_df["title"] = cleaned_titles
    output_df["match"] = title_similarity.round(2)

    output_df["has_updated_title"] = output_df["title"].fillna("").astype(
        str
    ) != output_df["title_original"].fillna("").astype(str)
    output_df["has_updated_bgg_id"] = [
        id_changed(old_id, new_id)
        for old_id, new_id in zip(
            output_df["bgg_id_original"],
            output_df["bgg_id"],
            strict=False,
        )
    ]

    return output_df[OUTPUT_COLUMNS].copy(), title_similarity


def summarize_similarity(
    similarity: pd.Series,
    *,
    threshold: float,
) -> None:
    valid_scores = similarity.dropna().to_numpy(dtype=float)
    logger.info("Eligible rows with title similarity score: %s", len(valid_scores))
    if len(valid_scores) == 0:
        return

    for percentile in (5, 10, 25, 50, 75, 90, 95):
        value = float(np.percentile(valid_scores, percentile))
        logger.info("title_similarity_p%s=%.2f", percentile, value)

    above_threshold = int((valid_scores >= threshold).sum())
    logger.info(
        "title_similarity_ge_threshold=%s/%s (threshold=%.2f)",
        above_threshold,
        len(valid_scores),
        threshold,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a finalized PAX title-correction export from resolver output."
        )
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Input CSV path from resolve_existing_pax_titles.py.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output CSV path for cleaned title correction data.",
    )
    parser.add_argument(
        "--title-match-threshold",
        type=float,
        default=70.0,
        help=(
            "Minimum title similarity score required to replace title with new_bgg_name "
            "for eligible rows."
        ),
    )
    parser.add_argument(
        "--manual-fixes",
        default=None,
        help=(
            "Manual title-fix CSV treated as ground truth for title_id -> bgg_id/new_bgg_id."
        ),
    )
    parser.add_argument(
        "--keep-name",
        default=None,
        help=("CSV list of title_ids where original title must always be kept."),
    )
    parser.add_argument(
        "--ranks",
        default=None,
        help="BGG ranks CSV path used to resolve canonical names for manual fixes.",
    )
    parser.add_argument(
        "--title-similarity-metric",
        choices=["token_sort", "token_set", "ratio", "wratio"],
        default="token_sort",
        help="Similarity metric used for title replacement scoring.",
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

    input_path = Path(args.input)
    output_path = Path(args.output)

    source_df = pd.read_csv(input_path)
    logger.info("Loaded %s rows from %s", len(source_df), input_path)
    manual_title_fixes = (
        load_manual_title_fixes(Path(args.manual_fixes)) if args.manual_fixes else {}
    )
    keep_name_title_ids = (
        load_title_id_set(Path(args.keep_name)) if args.keep_name else set()
    )
    bgg_name_lookup = load_bgg_name_lookup(Path(args.ranks)) if args.ranks else {}

    cleaned_df, title_similarity = build_cleaned_dataframe(
        source_df,
        title_match_threshold=args.title_match_threshold,
        title_similarity_metric=args.title_similarity_metric,
        manual_title_fixes=manual_title_fixes,
        keep_name_title_ids=keep_name_title_ids,
        bgg_name_lookup=bgg_name_lookup,
    )

    summarize_similarity(title_similarity, threshold=args.title_match_threshold)
    logger.info(
        "Rows with updated title: %s", int(cleaned_df["has_updated_title"].sum())
    )
    logger.info(
        "Rows with updated bgg_id: %s", int(cleaned_df["has_updated_bgg_id"].sum())
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned_df.to_csv(output_path, index=False)
    logger.info("Wrote cleaned output to %s (%s rows)", output_path, len(cleaned_df))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
