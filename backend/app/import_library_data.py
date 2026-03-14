"""
Library Data Import Script for Board Game Recommender

This script imports the Library tabletop games data into the backend database.
It handles the creation of Library game records and links them to existing BoardGame records.
"""

import pandas as pd
from pathlib import Path
from sqlalchemy.orm import Session
import sys
import argparse
import logging

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent
project_root = backend_dir.parent
sys.path.append(str(backend_dir))

from app import models, schemas  # noqa: E402
from app.database import SessionLocal, engine, SQLALCHEMY_DATABASE_URL  # noqa: E402
from app.logging_utils import build_log_handlers  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=build_log_handlers("import_library_data.log"),
)
logger = logging.getLogger(__name__)

BATCH_SIZE = 200  # Number of games to process before committing


def run_image_sync_library_only() -> bool:
    """Trigger optional image sync for Library games after Library import."""
    command = [
        sys.executable,
        "-m",
        "data_pipeline.src.assets.sync_fly_images",
        "--scope",
        "library-only",
    ]
    log_label = "Fly-local image sync"

    logger.info("Running %s command: %s", log_label, " ".join(command))

    import subprocess

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        if result.stdout:
            logger.info("%s stdout: %s", log_label, result.stdout)
        if result.stderr:
            logger.info("%s stderr: %s", log_label, result.stderr)
        return True
    except subprocess.CalledProcessError as exc:
        logger.error("%s failed with code %s", log_label, exc.returncode)
        logger.error("%s stdout: %s", log_label, exc.stdout)
        logger.error("%s stderr: %s", log_label, exc.stderr)
        return False


def create_library_game_record(game_data: pd.Series) -> models.LibraryGame:
    """Create a Library game record from the data without saving to database."""
    # Handle empty bgg_id values
    bgg_id = None
    if pd.notna(game_data["bgg_id"]) and game_data["bgg_id"] != "":
        try:
            bgg_id = int(game_data["bgg_id"])
        except (ValueError, TypeError):
            bgg_id = None

    # Handle empty min_titles_id values
    min_titles_id = None
    if pd.notna(game_data["min_titles_id"]) and game_data["min_titles_id"] != "":
        try:
            min_titles_id = int(game_data["min_titles_id"])
        except (ValueError, TypeError):
            min_titles_id = None

    # Handle empty convention_year values
    convention_year = None
    if pd.notna(game_data["convention_year"]) and game_data["convention_year"] != "":
        try:
            convention_year = int(game_data["convention_year"])
        except (ValueError, TypeError):
            convention_year = None

    # Handle empty year_title_first_added values
    year_title_first_added = None
    if (
        pd.notna(game_data["year_title_first_added"])
        and game_data["year_title_first_added"] != ""
    ):
        try:
            year_title_first_added = int(game_data["year_title_first_added"])
        except (ValueError, TypeError):
            year_title_first_added = None

    library_game_create = schemas.LibraryGameCreate(
        name=game_data["name"],
        name_raw=None
        if pd.isna(game_data["name_raw"]) or game_data["name_raw"] == ""
        else game_data["name_raw"],
        bgg_id=bgg_id,
        publisher=None
        if pd.isna(game_data["publisher"]) or game_data["publisher"] == ""
        else game_data["publisher"],
        min_titles_id=min_titles_id,
        titles_id_list=None
        if pd.isna(game_data["titles_id_list"]) or game_data["titles_id_list"] == ""
        else game_data["titles_id_list"],
        convention_name=None
        if pd.isna(game_data["convention_name"]) or game_data["convention_name"] == ""
        else game_data["convention_name"],
        convention_year=convention_year,
        year_title_first_added=year_title_first_added,
    )
    return models.LibraryGame(**library_game_create.model_dump())


def process_library_game_batch(games_batch: pd.DataFrame, db: Session) -> None:
    """Process a batch of Library games."""
    try:
        # Create all Library game records
        library_games = [
            create_library_game_record(game_data)
            for _, game_data in games_batch.iterrows()
        ]
        db.bulk_save_objects(library_games)
        db.commit()

    except Exception as e:
        db.rollback()
        raise e


def import_library_data(data_dir: str, delete_existing: bool = False) -> None:
    """
    Import Library tabletop games data into the database.

    Args:
        data_dir (str): Directory containing the Library data files
        delete_existing (bool): If True, deletes existing Library games before import
    """
    logger.info(f"Starting Library data import from {data_dir}")

    # Keep Alembic as schema authority for Postgres deployments.
    if SQLALCHEMY_DATABASE_URL.startswith("sqlite:///"):
        logger.info("Ensuring SQLite tables exist before import...")
        models.Base.metadata.create_all(bind=engine)
    else:
        logger.info(
            "Skipping table creation for non-SQLite database. "
            "Run Alembic migrations before import."
        )

    # Find the most recent Library games file
    library_dir = Path(data_dir)
    if not library_dir.exists():
        raise FileNotFoundError(f"Library data directory not found: {data_dir}")

    library_files = list(library_dir.glob("bg_lib_games_*.csv"))
    if not library_files:
        raise FileNotFoundError(f"No Library games files found in {data_dir}")

    # Use mtime so files like bg_lib_games_unplugged_2024.csv remain valid.
    latest_file = max(library_files, key=lambda x: x.stat().st_mtime)
    logger.info(f"Using most recent Library games file: {latest_file}")

    # Read the Library data
    try:
        library_games_df = pd.read_csv(latest_file, sep="|", escapechar="\\")
        logger.info(
            f"Successfully loaded Library data for {len(library_games_df)} games"
        )
    except Exception as e:
        logger.error(f"Error reading Library data file: {str(e)}")
        raise

    # Delete existing Library games if requested
    if delete_existing:
        db = SessionLocal()
        try:
            db.query(models.LibraryGame).delete()
            db.commit()
            logger.info("Deleted existing Library games")
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting existing Library games: {str(e)}")
            raise
        finally:
            db.close()

    # Process games in batches
    num_games = len(library_games_df)
    num_batches = (num_games + BATCH_SIZE - 1) // BATCH_SIZE

    # Create database session
    db = SessionLocal()
    try:
        for i in range(num_batches):
            start_idx = i * BATCH_SIZE
            end_idx = min((i + 1) * BATCH_SIZE, num_games)
            batch = library_games_df.iloc[start_idx:end_idx]

            try:
                process_library_game_batch(batch, db)
                logger.info(
                    f"Processed batch {i + 1}/{num_batches} (games {start_idx + 1}-{end_idx})"
                )
            except Exception as e:
                logger.error(f"Error processing batch {i + 1}: {str(e)}")
                raise e

        logger.info(f"Successfully imported {num_games} Library games")

        # Log some statistics
        if num_games > 0:
            games_with_bgg_id = library_games_df[
                library_games_df["bgg_id"].notna() & (library_games_df["bgg_id"] != "")
            ]
            logger.info(f"Games with BGG ID: {len(games_with_bgg_id)}")
            logger.info(f"Games without BGG ID: {num_games - len(games_with_bgg_id)}")

            if len(games_with_bgg_id) > 0:
                # Check how many of these BGG IDs exist in the BoardGame table
                bgg_ids = games_with_bgg_id["bgg_id"].astype(int).tolist()
                existing_games = (
                    db.query(models.BoardGame)
                    .filter(models.BoardGame.id.in_(bgg_ids))
                    .count()
                )
                logger.info(
                    f"Library games that link to existing BoardGame records: {existing_games}"
                )
                logger.info(
                    f"Library games with BGG ID but no matching BoardGame: {len(games_with_bgg_id) - existing_games}"
                )

    finally:
        db.close()


def main():
    """Main function to import the most recent Library data."""
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Import Library tabletop games data into the database"
    )
    parser.add_argument(
        "--delete-existing",
        action="store_true",
        help="Delete existing Library games before import",
    )
    parser.add_argument(
        "--sync-images",
        action="store_true",
        help="After import, run image sync for Library games.",
    )
    args = parser.parse_args()

    # Get the Library data directory
    library_data_dir = project_root / "data" / "library"
    if not library_data_dir.exists():
        raise FileNotFoundError(f"Library data directory not found: {library_data_dir}")

    # Import the data with delete_existing from command line args
    import_library_data(str(library_data_dir), delete_existing=args.delete_existing)

    if args.sync_images:
        if run_image_sync_library_only():
            logger.info("Image sync completed successfully after Library import.")
        else:
            logger.error("Image sync failed after Library import.")


if __name__ == "__main__":
    main()
