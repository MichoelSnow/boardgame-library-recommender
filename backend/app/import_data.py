"""
Data Import Script for Board Game Recommender

This script imports the processed crawler data into the backend database.
It handles the creation of all related entities (mechanics, categories, etc.).
"""

import pandas as pd
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.orm import Session
import sys
import argparse
import logging
import os
from typing import Dict, List, Any

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent
project_root = backend_dir.parent
sys.path.append(str(backend_dir))

from app import models, schemas  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.importers import import_all_data_postgres  # noqa: E402
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
IMPORT_DATA_ADVISORY_LOCK_ID = 94321077
IMPORT_TABLES = [
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


def acquire_import_data_lock():
    """
    Acquire a process-wide import lock.

    Uses a Postgres advisory lock to prevent concurrent import_data runs.
    Returns an open connection holding the lock, or None for non-Postgres engines.
    """
    dialect_name = getattr(engine.dialect, "name", "").lower()
    if dialect_name != "postgresql":
        return None

    lock_connection = engine.connect()
    try:
        acquired = bool(
            lock_connection.execute(
                text("SELECT pg_try_advisory_lock(:lock_id)"),
                {"lock_id": IMPORT_DATA_ADVISORY_LOCK_ID},
            ).scalar()
        )
    except Exception:
        lock_connection.close()
        raise
    if not acquired:
        lock_connection.close()
        raise RuntimeError(
            "Another import_data run is already active. "
            "Wait for it to finish, or stop it before starting a new import."
        )
    # End the transaction opened by the SELECT while keeping the session lock.
    try:
        lock_connection.commit()
    except Exception:
        lock_connection.close()
        raise
    return lock_connection


def release_import_data_lock(lock_connection) -> None:
    if lock_connection is None:
        return
    try:
        lock_connection.execute(
            text("SELECT pg_advisory_unlock(:lock_id)"),
            {"lock_id": IMPORT_DATA_ADVISORY_LOCK_ID},
        )
        lock_connection.commit()
    finally:
        lock_connection.close()


def _dedupe_relation_rows_by_name(
    relation_df: pd.DataFrame, *, game_id: int, name_column: str
) -> pd.DataFrame:
    game_rows = relation_df[relation_df["game_id"] == game_id]
    if game_rows.empty:
        return game_rows
    non_null_rows = game_rows[game_rows[name_column].notna()]
    return non_null_rows.drop_duplicates(subset=[name_column], keep="first")


def dedupe_games_dataframe(games_df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    duplicate_game_id_count = int(games_df.duplicated(subset=["id"]).sum())
    if duplicate_game_id_count == 0:
        return games_df, 0
    return games_df.drop_duplicates(
        subset=["id"], keep="first"
    ), duplicate_game_id_count


def run_image_sync(max_rank: int) -> bool:
    """Trigger optional image sync for qualifying games after import."""
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


def clear_import_tables_for_reimport() -> None:
    """
    Remove existing imported data without dropping schema objects.

    Uses ordered DELETE to avoid FK/TRUNCATE edge cases with preserved tables.
    """
    db = SessionLocal()
    try:
        dialect_name = getattr(engine.dialect, "name", "").lower()
        if dialect_name == "postgresql":
            truncate_tables = [table.name for table in IMPORT_TABLES]
            table_list_sql = ", ".join(truncate_tables)
            db.execute(
                text(f"TRUNCATE TABLE {table_list_sql} RESTART IDENTITY CASCADE")
            )
        else:
            # SQLite path: delete child tables first, then games (already ordered above).
            for table in IMPORT_TABLES:
                db.execute(text(f"DELETE FROM {table.name}"))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


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
        unique_mechanics_df = _dedupe_relation_rows_by_name(
            mechanics_df,
            game_id=game_id,
            name_column="boardgamemechanic_name",
        )
        mechanics = [
            models.Mechanic(
                game_id=game_id,
                boardgamemechanic_id=row["boardgamemechanic_id"],
                boardgamemechanic_name=row["boardgamemechanic_name"],
            )
            for _, row in unique_mechanics_df.iterrows()
        ]
        related_objects.extend(mechanics)

    # Add categories
    if "boardgamecategory" in related_data:
        categories_df = related_data["boardgamecategory"]
        unique_categories_df = _dedupe_relation_rows_by_name(
            categories_df,
            game_id=game_id,
            name_column="boardgamecategory_name",
        )
        categories = [
            models.Category(
                game_id=game_id,
                boardgamecategory_id=row["boardgamecategory_id"],
                boardgamecategory_name=row["boardgamecategory_name"],
            )
            for _, row in unique_categories_df.iterrows()
        ]
        related_objects.extend(categories)

    # Add designers
    if "boardgamedesigner" in related_data:
        designers_df = related_data["boardgamedesigner"]
        unique_designers_df = _dedupe_relation_rows_by_name(
            designers_df,
            game_id=game_id,
            name_column="boardgamedesigner_name",
        )
        designers = [
            models.Designer(
                game_id=game_id,
                boardgamedesigner_id=row["boardgamedesigner_id"],
                boardgamedesigner_name=row["boardgamedesigner_name"],
            )
            for _, row in unique_designers_df.iterrows()
        ]
        related_objects.extend(designers)

    # Add artists
    if "boardgameartist" in related_data:
        artists_df = related_data["boardgameartist"]
        unique_artists_df = _dedupe_relation_rows_by_name(
            artists_df,
            game_id=game_id,
            name_column="boardgameartist_name",
        )
        artists = [
            models.Artist(
                game_id=game_id,
                boardgameartist_id=row["boardgameartist_id"],
                boardgameartist_name=row["boardgameartist_name"],
            )
            for _, row in unique_artists_df.iterrows()
        ]
        related_objects.extend(artists)

    # Add publishers
    if "boardgamepublisher" in related_data:
        publishers_df = related_data["boardgamepublisher"]
        unique_publishers_df = _dedupe_relation_rows_by_name(
            publishers_df,
            game_id=game_id,
            name_column="boardgamepublisher_name",
        )
        publishers = [
            models.Publisher(
                game_id=game_id,
                boardgamepublisher_id=row["boardgamepublisher_id"],
                boardgamepublisher_name=row["boardgamepublisher_name"],
            )
            for _, row in unique_publishers_df.iterrows()
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

    # If requested, clear only the data related to imported datasets
    # (preserve users and library tables/schema).
    if delete_existing:
        logger.info(
            "Clearing existing import-related data (preserving users and library tables)..."
        )
        clear_import_tables_for_reimport()
        logger.info("Import-related data cleared")

    if getattr(engine.dialect, "name", "").lower() == "postgresql":
        logger.info("Using Postgres-optimized importer path.")
        import_all_data_postgres(
            engine=engine,
            data_dir=data_dir,
            timestamp=timestamp,
            logger=logger,
        )
        if delete_existing:
            logger.info("Running post-import SQL scripts...")
            if run_post_import_scripts():
                logger.info("Post-import SQL scripts completed successfully")
            else:
                logger.error("Some data calculations may be incomplete")
        return

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

        games_df, duplicate_game_id_count = dedupe_games_dataframe(games_df)
        if duplicate_game_id_count > 0:
            logger.warning(
                "Detected %s duplicate game id rows in processed_games_data; keeping first occurrence per id.",
                duplicate_game_id_count,
            )

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
        "--sync-images-max-rank",
        type=int,
        default=10000,
        help="Top-rank cutoff for qualifying image sync candidates (default: 10000).",
    )
    args = parser.parse_args()

    # Resolve processed-data root directory.
    configured_root = os.getenv("PROCESSED_DATA_ROOT")
    candidate_dirs: list[Path] = []
    if configured_root:
        candidate_dirs.append(Path(configured_root))
    candidate_dirs.extend(
        [
            Path("/data/transform/processed"),
            project_root / "data" / "transform" / "processed",
        ]
    )

    processed_root_dir = next((path for path in candidate_dirs if path.exists()), None)
    if processed_root_dir is None:
        candidate_text = ", ".join(str(path) for path in candidate_dirs)
        raise FileNotFoundError(
            f"Processed data root directory not found. Checked: {candidate_text}"
        )
    logger.info("Using processed data root directory: %s", processed_root_dir)

    # Find the most recent timestamped processed directory.
    timestamp_dirs = [
        p for p in processed_root_dir.iterdir() if p.is_dir() and p.name.isdigit()
    ]
    if not timestamp_dirs:
        raise FileNotFoundError(
            f"No timestamped processed directories found in {processed_root_dir}"
        )
    latest_dir = max(timestamp_dirs, key=lambda p: int(p.name))
    timestamp = int(latest_dir.name)
    latest_file = latest_dir / f"processed_games_data_{timestamp}.csv"
    if not latest_file.exists():
        raise FileNotFoundError(
            f"Missing expected processed games file in {latest_dir}: {latest_file.name}"
        )
    logger.info(f"Using most recent processed games file: {latest_file}")

    lock_connection = acquire_import_data_lock()
    try:
        # Import the data with delete_existing from command line args
        import_all_data(
            str(latest_dir), timestamp, delete_existing=args.delete_existing
        )

        if args.sync_images:
            if run_image_sync(max_rank=args.sync_images_max_rank):
                logger.info("Image sync completed successfully after data import.")
            else:
                logger.error("Image sync failed after data import.")
    finally:
        release_import_data_lock(lock_connection)


if __name__ == "__main__":
    main()
