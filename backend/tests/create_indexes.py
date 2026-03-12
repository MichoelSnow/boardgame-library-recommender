"""
Database Index Creation Script

This script adds essential indexes to improve query performance for the board game recommender.
Only indexes that are actually used in queries are created to avoid performance overhead.
"""

import sqlite3
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_indexes():
    """Create essential indexes for better query performance."""

    # Get database path
    backend_dir = Path(__file__).parent.parent
    database_path = backend_dir / "database" / "boardgames.db"

    if not database_path.exists():
        logger.error(f"Database not found at {database_path}")
        return

    # Connect to database
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    try:
        logger.info("Dropping unnecessary indexes...")

        # Drop indexes that are no longer needed
        indexes_to_drop = [
            # Games table - unnecessary fields
            "idx_games_year_published",
            "idx_games_playing_time",
            "idx_games_min_age",
            "idx_games_num_ratings",
            "idx_games_owned",
            # Note: idx_games_name is kept for search functionality
            # Relationship tables - unnecessary name fields
            "idx_mechanics_name",
            "idx_categories_name",
            "idx_designers_name",
            "idx_artists_name",
            "idx_publishers_game_id",
            "idx_publishers_boardgamepublisher_id",
            "idx_publishers_name",
            # PAX games - unnecessary fields
            "idx_pax_games_convention_name",
            "idx_pax_games_convention_year",
            "idx_pax_games_name",
        ]

        for index_name in indexes_to_drop:
            try:
                cursor.execute(f"DROP INDEX IF EXISTS {index_name}")
                logger.info(f"Dropped index: {index_name}")
            except Exception as e:
                logger.warning(f"Could not drop index {index_name}: {str(e)}")

        logger.info("Creating essential indexes...")

        # Games table - indexes for fields actually used in queries
        logger.info("Creating indexes for games table...")

        # Primary sort fields (used in ORDER BY) - ALL ranking fields
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_rank ON games(rank)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_average ON games(average)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_games_average_weight ON games(average_weight)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_games_year_published ON games(year_published)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_games_abstracts_rank ON games(abstracts_rank)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_games_cgs_rank ON games(cgs_rank)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_games_childrens_games_rank ON games(childrens_games_rank)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_games_family_games_rank ON games(family_games_rank)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_games_party_games_rank ON games(party_games_rank)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_games_strategy_games_rank ON games(strategy_games_rank)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_games_thematic_rank ON games(thematic_rank)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_games_wargames_rank ON games(wargames_rank)"
        )

        # Search field (used in ILIKE search)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_games_name_lower ON games(LOWER(name))"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_name ON games(name)")

        # Filter fields (used in WHERE clauses)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_games_min_players ON games(min_players)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_games_max_players ON games(max_players)"
        )

        # Relationship tables - only indexes for fields used in JOINs and filters
        logger.info("Creating indexes for relationship tables...")

        # Mechanics (used in subqueries and filters)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_mechanics_game_id ON mechanics(game_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_mechanics_boardgamemechanic_id ON mechanics(boardgamemechanic_id)"
        )

        # Categories (used in subqueries and filters)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_categories_game_id ON categories(game_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_categories_boardgamecategory_id ON categories(boardgamecategory_id)"
        )

        # Designers (used in subqueries and filters)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_designers_game_id ON designers(game_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_designers_boardgamedesigner_id ON designers(boardgamedesigner_id)"
        )

        # Artists (used in subqueries and filters)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_artists_game_id ON artists(game_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_artists_boardgameartist_id ON artists(boardgameartist_id)"
        )

        # Suggested Players (used in JOINs and filters)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_suggested_players_game_id ON suggested_players(game_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_suggested_players_player_count ON suggested_players(player_count)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_suggested_players_recommendation_level ON suggested_players(recommendation_level)"
        )

        # PAX Games - only bgg_id index
        logger.info("Creating indexes for PAX games table...")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_pax_games_bgg_id ON pax_games(bgg_id)"
        )

        # Commit changes
        conn.commit()
        logger.info("Essential indexes created successfully!")

        # Show index information
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        )
        indexes = cursor.fetchall()
        logger.info(f"Created {len(indexes)} essential indexes:")
        for index in indexes:
            logger.info(f"  - {index[0]}")

    except Exception as e:
        logger.error(f"Error creating indexes: {str(e)}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    create_indexes()
