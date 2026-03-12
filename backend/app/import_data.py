"""
Data Import Script for Board Game Recommender

This script imports the processed crawler data into the backend database.
It handles the creation of all related entities (mechanics, categories, etc.).
"""

import pandas as pd
from pathlib import Path
from sqlalchemy.orm import Session
import sys
import argparse
import logging
from typing import Dict, List, Any

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent
project_root = backend_dir.parent
sys.path.append(str(backend_dir))

from app import models, schemas  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.logging_utils import build_log_handlers  # noqa: E402


# We'll use a function to run SQL scripts after import
def run_post_import_scripts():
    """Run all SQL scripts in the scripts/sql directory."""
    # Import here to avoid circular imports
    sql_runner_path = backend_dir / "scripts" / "sql_runner.py"
    if not sql_runner_path.exists():
        logger.error(f"SQL runner script not found at {sql_runner_path}")
        return False

    # Use subprocess to run the SQL runner
    import subprocess

    try:
        result = subprocess.run(
            [sys.executable, str(sql_runner_path), "--all"],
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info(f"SQL runner output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running SQL scripts: {e}")
        logger.error(f"SQL runner stderr: {e.stderr}")
        return False


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=build_log_handlers("import_data.log"),
)
logger = logging.getLogger(__name__)

BATCH_SIZE = 200  # Number of games to process before committing


def run_image_sync(max_rank: int, backend: str) -> bool:
    """Trigger optional image sync for qualifying games after import."""
    if backend == "fly_local":
        command = [
            sys.executable,
            "-m",
            "data_pipeline.src.assets.sync_fly_images",
            "--scope",
            "all-qualified",
            "--max-rank",
            str(max_rank),
        ]
        log_label = "Fly-local image sync"
    elif backend == "r2_cdn":
        command = [
            sys.executable,
            "-m",
            "data_pipeline.src.assets.sync_r2_images",
            "--scope",
            "all-qualified",
            "--max-rank",
            str(max_rank),
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


def create_game_record(game_data: pd.Series) -> models.BoardGame:
    """Create a game record from the data without saving to database."""
    game_create = schemas.BoardGameCreate(
        id=game_data["id"],
        name=game_data["name"],
        description=None
        if pd.isna(game_data["description"])
        else game_data["description"],
        rank=None if pd.isna(game_data["rank"]) else int(game_data["rank"]),
        thumbnail=None if pd.isna(game_data["thumbnail"]) else game_data["thumbnail"],
        image=None if pd.isna(game_data["image"]) else game_data["image"],
        min_players=game_data["minplayers"],
        max_players=game_data["maxplayers"],
        playing_time=game_data["playingtime"],
        min_playtime=game_data["minplaytime"],
        max_playtime=game_data["maxplaytime"],
        min_age=game_data["minage"],
        year_published=game_data["yearpublished"],
        average=game_data["average"],
        num_ratings=game_data["numratings"],
        num_comments=game_data["numcomments"],
        num_weights=game_data["numweights"],
        average_weight=game_data["averageweight"],
        stddev=game_data["stddev"],
        median=game_data["median"],
        owned=game_data["owned"],
        trading=game_data["trading"],
        wanting=game_data["wanting"],
        wishing=game_data["wishing"],
        bayes_average=game_data["bayesaverage"],
        users_rated=game_data["usersrated"],
        is_expansion=game_data["is_expansion"],
        abstracts_rank=None
        if pd.isna(game_data["abstracts_rank"])
        else int(game_data["abstracts_rank"]),
        cgs_rank=None if pd.isna(game_data["cgs_rank"]) else int(game_data["cgs_rank"]),
        childrens_games_rank=None
        if pd.isna(game_data["childrensgames_rank"])
        else int(game_data["childrensgames_rank"]),
        family_games_rank=None
        if pd.isna(game_data["familygames_rank"])
        else int(game_data["familygames_rank"]),
        party_games_rank=None
        if pd.isna(game_data["partygames_rank"])
        else int(game_data["partygames_rank"]),
        strategy_games_rank=None
        if pd.isna(game_data["strategygames_rank"])
        else int(game_data["strategygames_rank"]),
        thematic_rank=None
        if pd.isna(game_data["thematic_rank"])
        else int(game_data["thematic_rank"]),
        wargames_rank=None
        if pd.isna(game_data["wargames_rank"])
        else int(game_data["wargames_rank"]),
    )
    return models.BoardGame(**game_create.model_dump())


def create_related_objects(
    game_id: int, game_data: pd.Series, related_data: Dict[str, pd.DataFrame]
) -> List[Any]:
    """Create all related objects for a game without saving to database."""
    related_objects = []

    # Add mechanics
    if "boardgamemechanic" in related_data:
        mechanics_df = related_data["boardgamemechanic"]
        mechanics = [
            models.Mechanic(
                game_id=game_id,
                boardgamemechanic_id=row["boardgamemechanic_id"],
                boardgamemechanic_name=row["boardgamemechanic_name"],
            )
            for _, row in mechanics_df[mechanics_df["game_id"] == game_id].iterrows()
        ]
        related_objects.extend(mechanics)

    # Add categories
    if "boardgamecategory" in related_data:
        categories_df = related_data["boardgamecategory"]
        categories = [
            models.Category(
                game_id=game_id,
                boardgamecategory_id=row["boardgamecategory_id"],
                boardgamecategory_name=row["boardgamecategory_name"],
            )
            for _, row in categories_df[categories_df["game_id"] == game_id].iterrows()
        ]
        related_objects.extend(categories)

    # Add designers
    if "boardgamedesigner" in related_data:
        designers_df = related_data["boardgamedesigner"]
        designers = [
            models.Designer(
                game_id=game_id,
                boardgamedesigner_id=row["boardgamedesigner_id"],
                boardgamedesigner_name=row["boardgamedesigner_name"],
            )
            for _, row in designers_df[designers_df["game_id"] == game_id].iterrows()
        ]
        related_objects.extend(designers)

    # Add artists
    if "boardgameartist" in related_data:
        artists_df = related_data["boardgameartist"]
        artists = [
            models.Artist(
                game_id=game_id,
                boardgameartist_id=row["boardgameartist_id"],
                boardgameartist_name=row["boardgameartist_name"],
            )
            for _, row in artists_df[artists_df["game_id"] == game_id].iterrows()
        ]
        related_objects.extend(artists)

    # Add publishers
    if "boardgamepublisher" in related_data:
        publishers_df = related_data["boardgamepublisher"]
        publishers = [
            models.Publisher(
                game_id=game_id,
                boardgamepublisher_id=row["boardgamepublisher_id"],
                boardgamepublisher_name=row["boardgamepublisher_name"],
            )
            for _, row in publishers_df[publishers_df["game_id"] == game_id].iterrows()
        ]
        related_objects.extend(publishers)

    # Add integrations
    if "boardgameintegration" in related_data:
        integrations_df = related_data["boardgameintegration"]
        integrations = [
            models.Integration(
                game_id=game_id,
                boardgameintegration_id=row["boardgameintegration_id"],
                boardgameintegration_name=row["boardgameintegration_name"],
            )
            for _, row in integrations_df[
                integrations_df["game_id"] == game_id
            ].iterrows()
        ]
        related_objects.extend(integrations)

    # Add implementations
    if "boardgameimplementation" in related_data:
        implementations_df = related_data["boardgameimplementation"]
        implementations = [
            models.Implementation(
                game_id=game_id,
                boardgameimplementation_id=row["boardgameimplementation_id"],
                boardgameimplementation_name=row["boardgameimplementation_name"],
            )
            for _, row in implementations_df[
                implementations_df["game_id"] == game_id
            ].iterrows()
        ]
        related_objects.extend(implementations)

    # Add compilations
    if "boardgamecompilation" in related_data:
        compilations_df = related_data["boardgamecompilation"]
        compilations = [
            models.Compilation(
                game_id=game_id,
                boardgamecompilation_id=row["boardgamecompilation_id"],
                boardgamecompilation_name=row["boardgamecompilation_name"],
            )
            for _, row in compilations_df[
                compilations_df["game_id"] == game_id
            ].iterrows()
        ]
        related_objects.extend(compilations)

    # Add expansions
    if "boardgameexpansion" in related_data:
        expansions_df = related_data["boardgameexpansion"]
        expansions = [
            models.Expansion(
                game_id=game_id,
                boardgameexpansion_id=row["boardgameexpansion_id"],
                boardgameexpansion_name=row["boardgameexpansion_name"],
            )
            for _, row in expansions_df[expansions_df["game_id"] == game_id].iterrows()
        ]
        related_objects.extend(expansions)

    # Add families
    if "boardgamefamily" in related_data:
        families_df = related_data["boardgamefamily"]
        families = [
            models.Family(
                game_id=game_id,
                boardgamefamily_id=row["boardgamefamily_id"],
                boardgamefamily_name=row["boardgamefamily_name"],
            )
            for _, row in families_df[families_df["game_id"] == game_id].iterrows()
        ]
        related_objects.extend(families)

    # Add versions
    if "versions" in related_data:
        versions_df = related_data["versions"]
        versions = [
            models.Version(
                game_id=game_id,
                version_id=row["version_id"],
                width=row["width"] if not pd.isna(row["width"]) else None,
                length=row["length"] if not pd.isna(row["length"]) else None,
                depth=row["depth"] if not pd.isna(row["depth"]) else None,
                year_published=row["year_published"]
                if not pd.isna(row["year_published"])
                else None,
                thumbnail=row["thumbnail"] if not pd.isna(row["thumbnail"]) else None,
                image=row["image"] if not pd.isna(row["image"]) else None,
                language=row["language"] if not pd.isna(row["language"]) else None,
                version_nickname=row["version_nickname"]
                if not pd.isna(row["version_nickname"])
                else None,
            )
            for _, row in versions_df[versions_df["game_id"] == game_id].iterrows()
        ]
        related_objects.extend(versions)

    # Add suggested number of players
    if "suggested_num_players" in related_data:
        players_df = related_data["suggested_num_players"]
        game_players = players_df[players_df["game_id"] == game_id]
        if not game_players.empty:
            suggested_players = [
                models.SuggestedPlayer(
                    game_id=game_id,
                    player_count=row["player_count"],
                    best=row["best"],
                    recommended=row["recommended"],
                    not_recommended=row["not_recommended"],
                    game_total_votes=row["game_total_votes"],
                    player_count_total_votes=row["total_votes"],
                    recommendation_level=row["recommendation_level"],
                )
                for _, row in game_players.iterrows()
            ]
            related_objects.extend(suggested_players)

    # Add language dependence
    if "language_dependence" in related_data:
        lang_df = related_data["language_dependence"]
        game_lang = lang_df[lang_df["id"] == game_id]
        if not game_lang.empty:
            row = game_lang.iloc[0]

            # Convert values to integers, handling any hex strings
            def convert_value(val):
                if isinstance(val, str) and val.startswith("0x"):
                    return int(val, 16)
                return int(float(val)) if pd.notna(val) else 0

            lang_dep = models.LanguageDependence(
                game_id=game_id,
                level_1=convert_value(row["1"]),
                level_2=convert_value(row["2"]),
                level_3=convert_value(row["3"]),
                level_4=convert_value(row["4"]),
                level_5=convert_value(row["5"]),
                total_votes=convert_value(row["total_votes"]),
                language_dependency=convert_value(row["language_dependency"]),
            )
            related_objects.append(lang_dep)

    return related_objects


def process_game_batch(
    games_batch: pd.DataFrame, related_data: Dict[str, pd.DataFrame], db: Session
) -> None:
    """Process a batch of games and their related data."""
    try:
        # Create all game records
        games = [
            create_game_record(game_data) for _, game_data in games_batch.iterrows()
        ]
        db.bulk_save_objects(games)
        db.flush()  # Flush to get the IDs

        # Create all related objects
        all_related_objects = []
        for game in games:
            related_objects = create_related_objects(
                game.id,
                games_batch.loc[games_batch["id"] == game.id].iloc[0],
                related_data,
            )
            all_related_objects.extend(related_objects)

        # Bulk save all related objects
        db.bulk_save_objects(all_related_objects)
        db.commit()

    except Exception as e:
        db.rollback()
        raise e


def import_all_data(
    data_dir: str, timestamp: int, delete_existing: bool = False
) -> None:
    """
    Import all processed game data into the database.

    Args:
        data_dir (str): Directory containing the processed data files
        timestamp (int): Timestamp used in the processed files
        delete_existing (bool): If True, deletes the existing database before import
    """
    logger.info(f"Starting data import from {data_dir}")

    # If requested, drop only the tables related to the imported datasets (preserve users and pax tables)
    if delete_existing:
        logger.info(
            "Dropping existing import-related tables (preserving users and pax tables)..."
        )
        tables_to_drop = [
            models.Mechanic.__table__,
            models.Category.__table__,
            models.Designer.__table__,
            models.Artist.__table__,
            models.Publisher.__table__,
            models.SuggestedPlayer.__table__,
            models.LanguageDependence.__table__,
            models.Integration.__table__,
            models.Implementation.__table__,
            models.Compilation.__table__,
            models.Expansion.__table__,
            models.Family.__table__,
            models.Version.__table__,
            models.BoardGame.__table__,
        ]
        # Drop children first, then parent (games)
        models.Base.metadata.drop_all(bind=engine, tables=tables_to_drop)
        logger.info("Import-related tables dropped")

    # Create database tables
    logger.info("Creating database tables...")
    models.Base.metadata.create_all(bind=engine)

    # Read all the processed data files
    try:
        # Read basic game data
        games_df = pd.read_csv(
            f"{data_dir}/processed_games_data_{timestamp}.csv", sep="|", escapechar="\\"
        )

        # Read related data files
        related_data = {}
        for entity in [
            "boardgamecategory",
            "boardgamemechanic",
            "boardgamedesigner",
            "boardgameartist",
            "boardgamepublisher",
            "boardgameintegration",
            "boardgameimplementation",
            "boardgamecompilation",
            "boardgameexpansion",
            "boardgamefamily",
            "suggested_num_players",
            "language_dependence",
            "versions",
        ]:
            try:
                related_data[entity] = pd.read_csv(
                    f"{data_dir}/processed_games_{entity}_{timestamp}.csv",
                    sep="|",
                    escapechar="\\",
                )
            except FileNotFoundError:
                logger.warning(f"File for {entity} not found, skipping...")

        logger.info(f"Successfully loaded data for {len(games_df)} games")
    except Exception as e:
        logger.error(f"Error reading data files: {str(e)}")
        raise

    # Process games in batches
    num_games = len(games_df)
    num_batches = (num_games + BATCH_SIZE - 1) // BATCH_SIZE

    # Create database session
    db = SessionLocal()
    try:
        for i in range(num_batches):
            start_idx = i * BATCH_SIZE
            end_idx = min((i + 1) * BATCH_SIZE, num_games)
            batch = games_df.iloc[start_idx:end_idx]

            try:
                process_game_batch(batch, related_data, db)
                logger.info(
                    f"Processed batch {i + 1}/{num_batches} (games {start_idx + 1}-{end_idx})"
                )
            except Exception as e:
                logger.error(f"Error processing batch {i + 1}: {str(e)}")
                raise e

        logger.info(f"Successfully imported {num_games} games")
    finally:
        db.close()

    # Run post-import SQL scripts if tables were recreated
    if delete_existing:
        logger.info("Running post-import SQL scripts...")
        if run_post_import_scripts():
            logger.info("Post-import SQL scripts completed successfully")
        else:
            logger.error("Some data calculations may be incomplete")


def main():
    """Main function to import the most recent processed data."""
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Import board game data into the database"
    )
    parser.add_argument(
        "--delete-existing",
        action="store_true",
        help="Delete existing database before import",
    )
    parser.add_argument(
        "--sync-images",
        action="store_true",
        help="After import, run image sync for qualifying games.",
    )
    parser.add_argument(
        "--sync-images-backend",
        choices=["fly_local", "r2_cdn"],
        default="fly_local",
        help="Image sync backend (default: fly_local).",
    )
    parser.add_argument(
        "--sync-images-r2",
        action="store_true",
        help="Deprecated alias for --sync-images --sync-images-backend r2_cdn.",
    )
    parser.add_argument(
        "--sync-images-max-rank",
        type=int,
        default=10000,
        help="Top-rank cutoff for qualifying image sync candidates (default: 10000).",
    )
    args = parser.parse_args()

    # Get the processed data directory
    data_dir = project_root / "data" / "processed"
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    # Find the most recent processed games file
    processed_files = list(data_dir.glob("processed_games_data_*.csv"))
    if not processed_files:
        raise FileNotFoundError(f"No processed games files found in {data_dir}")

    # Get the most recent file based on timestamp in filename
    latest_file = max(processed_files, key=lambda x: int(x.stem.split("_")[-1]))
    timestamp = int(latest_file.stem.split("_")[-1])
    logger.info(f"Using most recent processed games file: {latest_file}")

    # Import the data with delete_existing from command line args
    import_all_data(str(data_dir), timestamp, delete_existing=args.delete_existing)

    should_sync_images = args.sync_images or args.sync_images_r2
    sync_backend = "r2_cdn" if args.sync_images_r2 else args.sync_images_backend

    if should_sync_images:
        if run_image_sync(max_rank=args.sync_images_max_rank, backend=sync_backend):
            logger.info(
                "Image sync completed successfully after data import (backend=%s).",
                sync_backend,
            )
        else:
            logger.error(
                "Image sync failed after data import (backend=%s).",
                sync_backend,
            )


if __name__ == "__main__":
    main()
