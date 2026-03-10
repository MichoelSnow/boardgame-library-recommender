"""
PAX Data Import Script for Board Game Recommender

This script imports the PAX tabletop games data into the backend database.
It handles the creation of PAX game records and links them to existing BoardGame records.
"""

import pandas as pd
from pathlib import Path
from sqlalchemy.orm import Session
import sys
import argparse
import logging
from typing import Optional

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent
project_root = backend_dir.parent
sys.path.append(str(backend_dir))

from app import models, schemas, crud
from app.database import SessionLocal, engine
from app.logging_utils import build_log_handlers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=build_log_handlers("import_pax_data.log"),
)
logger = logging.getLogger(__name__)

BATCH_SIZE = 200  # Number of games to process before committing


def run_image_sync_pax_only(backend: str) -> bool:
    """Trigger optional image sync for PAX games after PAX import."""
    if backend == "fly_local":
        command = [
            sys.executable,
            "-m",
            "data_pipeline.src.assets.sync_fly_images",
            "--scope",
            "pax-only",
        ]
        log_label = "Fly-local image sync"
    elif backend == "r2_cdn":
        command = [
            sys.executable,
            "-m",
            "data_pipeline.src.assets.sync_r2_images",
            "--scope",
            "pax-only",
        ]
        log_label = "R2 image sync"
    else:
        logger.error("Unsupported image sync backend: %s", backend)
        return False

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

def create_pax_game_record(game_data: pd.Series) -> models.PAXGame:
    """Create a PAX game record from the data without saving to database."""
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
    if pd.notna(game_data["year_title_first_added"]) and game_data["year_title_first_added"] != "":
        try:
            year_title_first_added = int(game_data["year_title_first_added"])
        except (ValueError, TypeError):
            year_title_first_added = None
    
    pax_game_create = schemas.PAXGameCreate(
        name=game_data["name"],
        name_raw=None if pd.isna(game_data["name_raw"]) or game_data["name_raw"] == "" else game_data["name_raw"],
        bgg_id=bgg_id,
        publisher=None if pd.isna(game_data["publisher"]) or game_data["publisher"] == "" else game_data["publisher"],
        min_titles_id=min_titles_id,
        titles_id_list=None if pd.isna(game_data["titles_id_list"]) or game_data["titles_id_list"] == "" else game_data["titles_id_list"],
        convention_name=None if pd.isna(game_data["convention_name"]) or game_data["convention_name"] == "" else game_data["convention_name"],
        convention_year=convention_year,
        year_title_first_added=year_title_first_added
    )
    return models.PAXGame(**pax_game_create.model_dump())

def process_pax_game_batch(games_batch: pd.DataFrame, db: Session) -> None:
    """Process a batch of PAX games."""
    try:
        # Create all PAX game records
        pax_games = [create_pax_game_record(game_data) for _, game_data in games_batch.iterrows()]
        db.bulk_save_objects(pax_games)
        db.commit()
        
    except Exception as e:
        db.rollback()
        raise e

def import_pax_data(data_dir: str, delete_existing: bool = False) -> None:
    """
    Import PAX tabletop games data into the database.
    
    Args:
        data_dir (str): Directory containing the PAX data files
        delete_existing (bool): If True, deletes existing PAX games before import
    """
    logger.info(f"Starting PAX data import from {data_dir}")
    
    # Create database tables if they don't exist
    logger.info("Creating database tables...")
    models.Base.metadata.create_all(bind=engine)
    
    # Find the most recent PAX games file
    pax_dir = Path(data_dir)
    if not pax_dir.exists():
        raise FileNotFoundError(f"PAX data directory not found: {data_dir}")
    
    pax_files = list(pax_dir.glob("pax_tt_games_*.csv"))
    if not pax_files:
        raise FileNotFoundError(f"No PAX games files found in {data_dir}")
    
    # Get the most recent file based on timestamp in filename
    latest_file = max(pax_files, key=lambda x: int(x.stem.split('_')[-1]))
    logger.info(f"Using most recent PAX games file: {latest_file}")
    
    # Read the PAX data
    try:
        pax_games_df = pd.read_csv(latest_file, sep="|", escapechar="\\")
        logger.info(f"Successfully loaded PAX data for {len(pax_games_df)} games")
    except Exception as e:
        logger.error(f"Error reading PAX data file: {str(e)}")
        raise
    
    # Delete existing PAX games if requested
    if delete_existing:
        db = SessionLocal()
        try:
            db.query(models.PAXGame).delete()
            db.commit()
            logger.info("Deleted existing PAX games")
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting existing PAX games: {str(e)}")
            raise
        finally:
            db.close()
    
    # Process games in batches
    num_games = len(pax_games_df)
    num_batches = (num_games + BATCH_SIZE - 1) // BATCH_SIZE
    
    # Create database session
    db = SessionLocal()
    try:
        for i in range(num_batches):
            start_idx = i * BATCH_SIZE
            end_idx = min((i + 1) * BATCH_SIZE, num_games)
            batch = pax_games_df.iloc[start_idx:end_idx]
            
            try:
                process_pax_game_batch(batch, db)
                logger.info(f"Processed batch {i+1}/{num_batches} (games {start_idx+1}-{end_idx})")
            except Exception as e:
                logger.error(f"Error processing batch {i+1}: {str(e)}")
                raise e
        
        logger.info(f"Successfully imported {num_games} PAX games")
        
        # Log some statistics
        if num_games > 0:
            games_with_bgg_id = pax_games_df[pax_games_df['bgg_id'].notna() & (pax_games_df['bgg_id'] != '')]
            logger.info(f"Games with BGG ID: {len(games_with_bgg_id)}")
            logger.info(f"Games without BGG ID: {num_games - len(games_with_bgg_id)}")
            
            if len(games_with_bgg_id) > 0:
                # Check how many of these BGG IDs exist in the BoardGame table
                bgg_ids = games_with_bgg_id['bgg_id'].astype(int).tolist()
                existing_games = db.query(models.BoardGame).filter(models.BoardGame.id.in_(bgg_ids)).count()
                logger.info(f"PAX games that link to existing BoardGame records: {existing_games}")
                logger.info(f"PAX games with BGG ID but no matching BoardGame: {len(games_with_bgg_id) - existing_games}")
    
    finally:
        db.close()

def main():
    """Main function to import the most recent PAX data."""
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Import PAX tabletop games data into the database')
    parser.add_argument('--delete-existing', action='store_true', 
                      help='Delete existing PAX games before import')
    parser.add_argument(
        '--sync-images',
        action='store_true',
        help='After import, run image sync for PAX games.',
    )
    parser.add_argument(
        '--sync-images-backend',
        choices=['fly_local', 'r2_cdn'],
        default='fly_local',
        help='Image sync backend (default: fly_local).',
    )
    parser.add_argument(
        '--sync-images-r2',
        action='store_true',
        help='Deprecated alias for --sync-images --sync-images-backend r2_cdn.',
    )
    args = parser.parse_args()
    
    # Get the PAX data directory
    pax_data_dir = project_root / "data" / "pax"
    if not pax_data_dir.exists():
        raise FileNotFoundError(f"PAX data directory not found: {pax_data_dir}")
    
    # Import the data with delete_existing from command line args
    import_pax_data(str(pax_data_dir), delete_existing=args.delete_existing)

    should_sync_images = args.sync_images or args.sync_images_r2
    sync_backend = "r2_cdn" if args.sync_images_r2 else args.sync_images_backend

    if should_sync_images:
        if run_image_sync_pax_only(sync_backend):
            logger.info(
                "Image sync completed successfully after PAX import (backend=%s).",
                sync_backend,
            )
        else:
            logger.error(
                "Image sync failed after PAX import (backend=%s).",
                sync_backend,
            )

if __name__ == "__main__":
    main() 
