from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
from tqdm import tqdm

from .r2_sync import R2ImageSyncer, r2_config_available

try:
    from ..common.logging_utils import build_log_handlers
except ImportError:
    from data_pipeline.src.common.logging_utils import build_log_handlers


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=build_log_handlers("r2_image_sync.log"),
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DEFAULT_PAX_DIR = PROJECT_ROOT / "data" / "pax"


def parse_id_list(raw: str) -> set[int]:
    if not raw.strip():
        return set()
    ids: set[int] = set()
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        ids.add(int(token))
    return ids


def find_latest_processed_games_file(processed_dir: Path) -> Path:
    processed_files = list(processed_dir.glob("processed_games_data_*.csv"))
    if not processed_files:
        raise FileNotFoundError(f"No processed games files found in {processed_dir}")
    return max(processed_files, key=lambda path: int(path.stem.split("_")[-1]))


def find_latest_pax_file(pax_dir: Path) -> Optional[Path]:
    pax_files = list(pax_dir.glob("pax_tt_games_*.csv"))
    if not pax_files:
        return None
    return max(pax_files, key=lambda path: int(path.stem.split("_")[-1]))


def load_pax_bgg_ids(pax_file: Optional[Path]) -> set[int]:
    if not pax_file or not pax_file.exists():
        return set()
    pax_df = pd.read_csv(pax_file, sep="|", escapechar="\\")
    if "bgg_id" not in pax_df.columns:
        return set()

    ids = set()
    for value in pax_df["bgg_id"].dropna().tolist():
        value_str = str(value).strip()
        if not value_str:
            continue
        try:
            ids.add(int(float(value_str)))
        except ValueError:
            continue
    return ids


def qualifies_for_sync(
    *,
    game_id: int,
    game_rank: Optional[float],
    pax_ids: set[int],
    max_rank: int,
    scope: str,
) -> bool:
    is_pax = game_id in pax_ids
    is_top_ranked = game_rank is not None and game_rank <= max_rank

    if scope == "pax-only":
        return is_pax
    if scope == "top-rank-only":
        return is_top_ranked
    return is_pax or is_top_ranked


def iter_sync_candidates(
    games_df: pd.DataFrame,
    *,
    pax_ids: set[int],
    max_rank: int,
    scope: str,
    include_game_ids: set[int],
) -> Iterable[tuple[int, str]]:
    required_columns = {"id", "image"}
    missing = required_columns - set(games_df.columns)
    if missing:
        raise ValueError(f"Missing required columns in processed games data: {sorted(missing)}")

    filtered_df = games_df[games_df["image"].notna()].copy()

    if include_game_ids:
        filtered_df = filtered_df[filtered_df["id"].astype(int).isin(include_game_ids)]

    for _, row in filtered_df.iterrows():
        try:
            game_id = int(row["id"])
        except (ValueError, TypeError):
            continue

        rank_value = row.get("rank")
        game_rank: Optional[float] = None
        if pd.notna(rank_value):
            try:
                game_rank = float(rank_value)
            except (ValueError, TypeError):
                game_rank = None

        if not qualifies_for_sync(
            game_id=game_id,
            game_rank=game_rank,
            pax_ids=pax_ids,
            max_rank=max_rank,
            scope=scope,
        ):
            continue

        image_url = str(row["image"]).strip()
        if not image_url:
            continue

        yield game_id, image_url


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync qualifying game images to Cloudflare R2.")
    parser.add_argument(
        "--processed-file",
        type=Path,
        default=None,
        help="Explicit processed_games_data CSV path (defaults to latest file).",
    )
    parser.add_argument(
        "--pax-file",
        type=Path,
        default=None,
        help="Explicit pax_tt_games CSV path (defaults to latest file, if present).",
    )
    parser.add_argument(
        "--max-rank",
        type=int,
        default=10000,
        help="Top-rank cutoff for qualification (default: 10000).",
    )
    parser.add_argument(
        "--scope",
        choices=["all-qualified", "pax-only", "top-rank-only"],
        default="all-qualified",
        help="Qualification scope (default: all-qualified).",
    )
    parser.add_argument(
        "--include-game-ids",
        type=str,
        default="",
        help="Optional comma-separated game IDs to constrain candidate set before qualification.",
    )
    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="Upload and replace existing objects.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max number of candidates to process (0 = no limit).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List candidates without downloading/uploading.",
    )
    parser.add_argument(
        "--no-prefetch-existing",
        action="store_true",
        help="Disable existing-key prefetch and use per-ID existence checks only.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    processed_file = args.processed_file or find_latest_processed_games_file(DEFAULT_PROCESSED_DIR)
    pax_file = args.pax_file or find_latest_pax_file(DEFAULT_PAX_DIR)

    games_df = pd.read_csv(processed_file, sep="|", escapechar="\\")
    pax_ids = load_pax_bgg_ids(pax_file)
    include_game_ids = parse_id_list(args.include_game_ids)

    candidates = list(
        iter_sync_candidates(
            games_df,
            pax_ids=pax_ids,
            max_rank=args.max_rank,
            scope=args.scope,
            include_game_ids=include_game_ids,
        )
    )

    if args.limit and args.limit > 0:
        candidates = candidates[: args.limit]

    logger.info("Processed file: %s", processed_file)
    logger.info("PAX file: %s", pax_file or "none")
    logger.info("Scope: %s", args.scope)
    logger.info("Qualification max rank: %s", args.max_rank)
    logger.info("Candidates selected: %s", len(candidates))

    if args.dry_run:
        for game_id, image_url in candidates[:50]:
            logger.info("Dry run candidate: game_id=%s image=%s", game_id, image_url)
        if len(candidates) > 50:
            logger.info("Dry run output truncated at 50 candidates.")
        return 0

    if not r2_config_available():
        logger.error("R2 config is incomplete. Set R2_ENDPOINT_URL/R2_ACCESS_KEY_ID/R2_SECRET_ACCESS_KEY/R2_BUCKET_NAME.")
        return 1

    syncer = R2ImageSyncer.from_env()
    existing_key_map: dict[int, str] = {}
    prefetch_enabled = not args.no_prefetch_existing
    if prefetch_enabled:
        try:
            existing_keys = syncer.list_existing_game_keys(prefix="games/")
            existing_key_map = syncer.build_existing_bgg_id_map(existing_keys)
            logger.info(
                "Prefetched %s existing R2 game keys (%s distinct bgg_ids).",
                len(existing_keys),
                len(existing_key_map),
            )
        except Exception as exc:  # pragma: no cover - fallback safety
            logger.warning(
                "Existing-key prefetch failed (%s). Falling back to per-ID checks.",
                exc,
            )
            existing_key_map = {}
            prefetch_enabled = False

    uploaded_count = 0
    skipped_count = 0
    failed_count = 0

    for game_id, image_url in tqdm(candidates, desc="Syncing images to R2"):
        try:
            if prefetch_enabled and not args.overwrite_existing and game_id in existing_key_map:
                skipped_count += 1
                continue
            _, status = syncer.sync_image_url(
                bgg_id=game_id,
                image_url=image_url,
                overwrite_existing=args.overwrite_existing,
            )
            if status == "uploaded":
                uploaded_count += 1
            else:
                skipped_count += 1
        except Exception as exc:  # pragma: no cover - defensive logging
            failed_count += 1
            logger.warning(
                "Failed syncing image for game %s (%s): %s",
                game_id,
                image_url,
                exc,
            )

    logger.info(
        "R2 image sync complete. uploaded=%s skipped_existing=%s failed=%s total=%s",
        uploaded_count,
        skipped_count,
        failed_count,
        len(candidates),
    )

    return 1 if failed_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
