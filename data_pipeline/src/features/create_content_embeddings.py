import argparse
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.preprocessing import normalize

try:
    from ..common.logging_utils import build_log_handlers
except ImportError:
    from data_pipeline.src.common.logging_utils import build_log_handlers


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=build_log_handlers("content_embeddings.log"),
)
logger = logging.getLogger(__name__)


RELATION_SPECS = (
    ("mechanics", "processed_games_boardgamemechanic_{ts}.csv", "boardgamemechanic_id"),
    (
        "categories",
        "processed_games_boardgamecategory_{ts}.csv",
        "boardgamecategory_id",
    ),
    ("families", "processed_games_boardgamefamily_{ts}.csv", "boardgamefamily_id"),
    ("designers", "processed_games_boardgamedesigner_{ts}.csv", "boardgamedesigner_id"),
    ("artists", "processed_games_boardgameartist_{ts}.csv", "boardgameartist_id"),
    (
        "publishers",
        "processed_games_boardgamepublisher_{ts}.csv",
        "boardgamepublisher_id",
    ),
)


def resolve_embeddings_output_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "backend" / "database"


def resolve_processed_root() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "transform" / "processed"


def resolve_processed_timestamp(processed_root: Path) -> str:
    candidates = [
        p.name for p in processed_root.iterdir() if p.is_dir() and p.name.isdigit()
    ]
    if not candidates:
        raise FileNotFoundError(
            f"No timestamped processed dirs found under {processed_root}"
        )
    return max(candidates)


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, float) and np.isnan(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _playtime_bucket(minutes: Any) -> str | None:
    val = _safe_int(minutes)
    if val is None or val < 0:
        return None
    if val < 60:
        return "playtime:<60"
    if val <= 120:
        return "playtime:60-120"
    return "playtime:>120"


def _weight_bucket(avg_weight: Any) -> str | None:
    if avg_weight is None:
        return None
    try:
        weight = float(avg_weight)
    except (TypeError, ValueError):
        return None
    if np.isnan(weight):
        return None
    if weight <= 2.0:
        return "weight:beginner"
    if weight < 4.0:
        return "weight:midweight"
    return "weight:heavy"


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    return pd.read_csv(path, sep="|", escapechar="\\", low_memory=False)


def _add_feature(
    *,
    game_id: int,
    feature_name: str,
    weight: float,
    game_feature_weights: dict[int, dict[str, float]],
) -> None:
    if weight <= 0:
        return
    existing = game_feature_weights[game_id].get(feature_name, 0.0)
    # Multi-source features sum and get normalized later.
    game_feature_weights[game_id][feature_name] = existing + weight


def build_content_feature_matrix(
    *,
    processed_dir: Path,
    timestamp: str,
    strong_weight: float,
    medium_weight: float,
    light_weight: float,
    publisher_weight: float,
    include_not_recommended: bool,
) -> tuple[sparse.csr_matrix, dict[int, int], dict[int, str], dict[int, str]]:
    base_file = processed_dir / f"processed_games_data_{timestamp}.csv"
    base_df = _load_csv(base_file)
    required_base_cols = {"id", "playingtime", "averageweight"}
    missing = required_base_cols - set(base_df.columns)
    if missing:
        raise ValueError(f"Missing columns in {base_file}: {sorted(missing)}")

    game_ids = (
        pd.to_numeric(base_df["id"], errors="coerce").dropna().astype("int64").tolist()
    )
    game_ids = sorted(set(game_ids))
    game_to_row = {game_id: idx for idx, game_id in enumerate(game_ids)}
    row_to_game = {idx: game_id for game_id, idx in game_to_row.items()}

    game_feature_weights: dict[int, dict[str, float]] = defaultdict(dict)

    # Relation features (strong + publisher light).
    for relation_name, file_tmpl, id_col in RELATION_SPECS:
        relation_file = processed_dir / file_tmpl.format(ts=timestamp)
        if not relation_file.exists():
            logger.warning("Skipping missing relation file: %s", relation_file)
            continue
        rel_df = _load_csv(relation_file)
        if "game_id" not in rel_df.columns or id_col not in rel_df.columns:
            logger.warning(
                "Skipping relation file with missing columns: %s", relation_file
            )
            continue
        use_weight = (
            publisher_weight if relation_name == "publishers" else strong_weight
        )
        rel_df = rel_df[["game_id", id_col]].copy()
        rel_df["game_id"] = pd.to_numeric(rel_df["game_id"], errors="coerce")
        rel_df[id_col] = pd.to_numeric(rel_df[id_col], errors="coerce")
        rel_df = rel_df.dropna(subset=["game_id", id_col]).drop_duplicates()
        for row in rel_df.itertuples(index=False):
            gid = int(row.game_id)
            if gid not in game_to_row:
                continue
            feature_name = f"{relation_name}:{int(getattr(row, id_col))}"
            _add_feature(
                game_id=gid,
                feature_name=feature_name,
                weight=use_weight,
                game_feature_weights=game_feature_weights,
            )

    # Bucketed base features.
    for row in base_df.itertuples(index=False):
        gid = _safe_int(getattr(row, "id"))
        if gid is None or gid not in game_to_row:
            continue
        playtime_feature = _playtime_bucket(getattr(row, "playingtime"))
        if playtime_feature:
            _add_feature(
                game_id=gid,
                feature_name=playtime_feature,
                weight=medium_weight,
                game_feature_weights=game_feature_weights,
            )
        weight_feature = _weight_bucket(getattr(row, "averageweight"))
        if weight_feature:
            _add_feature(
                game_id=gid,
                feature_name=weight_feature,
                weight=medium_weight,
                game_feature_weights=game_feature_weights,
            )
    # Suggested players as medium signal.
    suggested_file = (
        processed_dir / f"processed_games_suggested_num_players_{timestamp}.csv"
    )
    if suggested_file.exists():
        suggested_df = _load_csv(suggested_file)
        if {"game_id", "player_count", "recommendation_level"} <= set(
            suggested_df.columns
        ):
            suggested_df = suggested_df[
                ["game_id", "player_count", "recommendation_level"]
            ].copy()
            suggested_df["game_id"] = pd.to_numeric(
                suggested_df["game_id"], errors="coerce"
            )
            suggested_df["player_count"] = pd.to_numeric(
                suggested_df["player_count"], errors="coerce"
            )
            suggested_df["recommendation_level"] = (
                suggested_df["recommendation_level"].astype(str).str.strip().str.lower()
            )
            suggested_df = suggested_df.dropna(subset=["game_id", "player_count"])
            allowed_levels = {"best", "recommended"}
            if include_not_recommended:
                allowed_levels.add("not_recommended")
            suggested_df = suggested_df[
                suggested_df["recommendation_level"].isin(allowed_levels)
            ].drop_duplicates()
            for row in suggested_df.itertuples(index=False):
                gid = int(row.game_id)
                if gid not in game_to_row:
                    continue
                level = str(row.recommendation_level)
                player_count = int(row.player_count)
                feature_name = f"suggested:{level}:{player_count}"
                _add_feature(
                    game_id=gid,
                    feature_name=feature_name,
                    weight=medium_weight,
                    game_feature_weights=game_feature_weights,
                )
        else:
            logger.warning(
                "Skipping suggested players features; missing columns in %s",
                suggested_file,
            )
    else:
        logger.warning("Skipping missing suggested players file: %s", suggested_file)

    # Build sparse matrix.
    all_features = sorted(
        {
            feature_name
            for feature_map in game_feature_weights.values()
            for feature_name in feature_map
        }
    )
    feature_to_col = {
        feature_name: idx for idx, feature_name in enumerate(all_features)
    }
    col_to_feature = {idx: feature_name for feature_name, idx in feature_to_col.items()}

    row_idx: list[int] = []
    col_idx: list[int] = []
    values: list[float] = []
    for gid, feature_map in game_feature_weights.items():
        ridx = game_to_row[gid]
        for feature_name, value in feature_map.items():
            if value <= 0:
                continue
            row_idx.append(ridx)
            col_idx.append(feature_to_col[feature_name])
            values.append(float(value))

    raw_matrix = sparse.coo_matrix(
        (values, (row_idx, col_idx)),
        shape=(len(game_to_row), len(feature_to_col)),
        dtype=np.float32,
    ).tocsr()

    content_matrix = normalize(raw_matrix, norm="l2", axis=1)
    return content_matrix, row_to_game, col_to_feature, game_to_row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create content-based game embeddings from processed pipeline outputs."
    )
    parser.add_argument(
        "--processed-root",
        type=Path,
        default=resolve_processed_root(),
        help="Root dir containing timestamped processed output directories.",
    )
    parser.add_argument(
        "--timestamp",
        type=str,
        default=None,
        help="Optional processed timestamp dir name. Uses latest when omitted.",
    )
    parser.add_argument(
        "--strong-weight",
        type=float,
        default=1.0,
        help="Weight for core strong factors (mechanics/categories/families/designers/artists).",
    )
    parser.add_argument(
        "--medium-weight",
        type=float,
        default=0.45,
        help="Weight for medium factors (suggested players, weight bucket, playtime bucket).",
    )
    parser.add_argument(
        "--light-weight",
        type=float,
        default=0.2,
        help="Legacy umbrella light factor weight (kept for compatibility in metadata).",
    )
    parser.add_argument(
        "--publisher-weight",
        type=float,
        default=0.2,
        help="Weight for publisher features.",
    )
    parser.add_argument(
        "--include-not-recommended",
        action="store_true",
        help="Include suggested-player not_recommended signals.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    processed_root: Path = args.processed_root
    timestamp = args.timestamp or resolve_processed_timestamp(processed_root)
    processed_dir = processed_root / timestamp
    if not processed_dir.exists():
        raise FileNotFoundError(f"Processed dir not found: {processed_dir}")

    logger.info("Building content embeddings from processed dir: %s", processed_dir)
    matrix, row_to_game, col_to_feature, game_to_row = build_content_feature_matrix(
        processed_dir=processed_dir,
        timestamp=timestamp,
        strong_weight=args.strong_weight,
        medium_weight=args.medium_weight,
        light_weight=args.light_weight,
        publisher_weight=args.publisher_weight,
        include_not_recommended=args.include_not_recommended,
    )

    output_dir = resolve_embeddings_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    matrix_path = output_dir / f"content_embeddings_{timestamp}.npz"
    game_map_path = output_dir / f"content_reverse_mappings_{timestamp}.json"
    feature_map_path = output_dir / f"content_feature_mappings_{timestamp}.json"
    metadata_path = output_dir / f"content_embeddings_metadata_{timestamp}.json"

    sparse.save_npz(matrix_path, matrix)
    with game_map_path.open("w", encoding="utf-8") as handle:
        json.dump(row_to_game, handle)
    with feature_map_path.open("w", encoding="utf-8") as handle:
        json.dump(col_to_feature, handle)
    with metadata_path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "timestamp": timestamp,
                "matrix_shape": [int(matrix.shape[0]), int(matrix.shape[1])],
                "nnz": int(matrix.nnz),
                "weights": {
                    "strong_weight": args.strong_weight,
                    "medium_weight": args.medium_weight,
                    "light_weight": args.light_weight,
                    "publisher_weight": args.publisher_weight,
                },
                "include_not_recommended": bool(args.include_not_recommended),
                "game_count": len(game_to_row),
                "feature_count": len(col_to_feature),
            },
            handle,
            indent=2,
            sort_keys=True,
        )

    logger.info("Saved content embeddings: %s", matrix_path)
    logger.info("Saved content game mappings: %s", game_map_path)
    logger.info("Saved content feature mappings: %s", feature_map_path)
    logger.info("Saved content metadata: %s", metadata_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
