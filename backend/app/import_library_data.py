"""
Library Data Import Script for Board Game Recommender.

Imports a legacy Library CSV into the modern library import tables
(`library_imports` + `library_import_items`).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent
project_root = backend_dir.parent
sys.path.append(str(backend_dir))

from app import crud, models  # noqa: E402
from app.database import SQLALCHEMY_DATABASE_URL, SessionLocal, engine  # noqa: E402
from app.logging_utils import build_log_handlers  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=build_log_handlers("import_library_data.log"),
)
logger = logging.getLogger(__name__)

DEFAULT_IMPORT_METHOD = "legacy_library_csv"


def _parse_bgg_id(raw_value: object) -> Optional[int]:
    if pd.isna(raw_value):
        return None

    text_value = str(raw_value).strip()
    if not text_value:
        return None

    try:
        numeric = int(float(text_value))
    except ValueError:
        return None

    if numeric <= 0:
        return None
    return numeric


def _extract_unique_bgg_ids(
    library_games_df: pd.DataFrame,
) -> tuple[list[int], int, int]:
    unique_ids: list[int] = []
    seen: set[int] = set()
    invalid_count = 0
    duplicate_count = 0

    for raw_value in library_games_df.get("bgg_id", []):
        parsed = _parse_bgg_id(raw_value)
        if parsed is None:
            invalid_count += 1
            continue
        if parsed in seen:
            duplicate_count += 1
            continue
        seen.add(parsed)
        unique_ids.append(parsed)

    return unique_ids, invalid_count, duplicate_count


def _resolve_import_user_id(db) -> int:
    first_user = db.query(models.User).order_by(models.User.id.asc()).first()
    if first_user is None:
        raise RuntimeError(
            "No users found. Create an admin user before importing library data."
        )
    return first_user.id


def _purge_existing_library_imports(db) -> None:
    db.query(models.LibraryImportItem).delete(synchronize_session=False)
    db.query(models.LibraryImport).delete(synchronize_session=False)
    db.commit()


def import_library_data(
    csv_path: str,
    *,
    label: Optional[str],
    delete_existing: bool,
    activate: bool,
) -> None:
    logger.info("Starting Library data import from %s", csv_path)

    # Keep Alembic as schema authority for Postgres deployments.
    if SQLALCHEMY_DATABASE_URL.startswith("sqlite:///"):
        logger.info("Ensuring SQLite tables exist before import...")
        models.Base.metadata.create_all(bind=engine)
    else:
        logger.info(
            "Skipping table creation for non-SQLite database. "
            "Run Alembic migrations before import."
        )

    source_file = Path(csv_path)
    if not source_file.exists():
        raise FileNotFoundError(f"Library CSV not found: {csv_path}")
    if source_file.suffix.lower() != ".csv":
        raise ValueError(f"Library source must be a CSV file: {csv_path}")

    try:
        library_games_df = pd.read_csv(source_file, sep="|", escapechar="\\")
    except Exception as exc:
        logger.error("Error reading Library data file: %s", exc)
        raise

    bgg_ids, invalid_count, duplicate_count = _extract_unique_bgg_ids(library_games_df)
    if not bgg_ids:
        raise ValueError("No valid BGG IDs found in library CSV.")

    import_label = label or source_file.stem

    db = SessionLocal()
    try:
        if delete_existing:
            _purge_existing_library_imports(db)
            logger.info("Deleted existing library imports and items")

        imported_by_user_id = _resolve_import_user_id(db)

        library_import = crud.create_library_import(
            db,
            label=import_label,
            import_method=DEFAULT_IMPORT_METHOD,
            imported_by_user_id=imported_by_user_id,
            bgg_ids=bgg_ids,
            activate=activate,
        )

        logger.info(
            "Created library import id=%s label=%s items=%s active=%s",
            library_import.id,
            library_import.label,
            len(bgg_ids),
            library_import.is_active,
        )
        logger.info(
            "Source rows=%s valid_ids=%s invalid_or_empty=%s duplicates_removed=%s",
            len(library_games_df),
            len(bgg_ids),
            invalid_count,
            duplicate_count,
        )
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import legacy Library CSV into library imports tables"
    )
    parser.add_argument(
        "--csv",
        required=True,
        help="Path to library CSV (pipe-delimited) with a bgg_id column.",
    )
    parser.add_argument(
        "--delete-existing",
        action="store_true",
        help="Delete existing library imports/items before creating the new import.",
    )
    parser.add_argument(
        "--label",
        default=None,
        help="Optional label for the new import (default: CSV filename stem).",
    )
    parser.add_argument(
        "--no-activate",
        action="store_true",
        help="Create the import without activating it.",
    )
    args = parser.parse_args()

    import_library_data(
        args.csv,
        label=args.label,
        delete_existing=args.delete_existing,
        activate=not args.no_activate,
    )


if __name__ == "__main__":
    main()
