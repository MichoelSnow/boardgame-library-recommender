"""
Database Query Test Script

This script tests that the database queries work without hanging.
"""

import logging
import sys
import time
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.append(str(backend_dir))

from app import crud  # noqa: E402
from app.database import SessionLocal  # noqa: E402


logger = logging.getLogger(__name__)


def test_basic_queries():
    """Test basic database queries to ensure they don't hang."""
    db = SessionLocal()

    try:
        logger.info("Testing basic queries...")

        # Test 1: Simple games query
        logger.info("1. Testing simple games query...")
        start_time = time.time()
        games, total = crud.get_games(db, skip=0, limit=10, sort_by="rank")
        end_time = time.time()
        logger.info(
            "Success: %d games in %.1fms",
            len(games),
            (end_time - start_time) * 1000,
        )

        # Test 2: Games with search
        logger.info("2. Testing games with search...")
        start_time = time.time()
        games, total = crud.get_games(
            db, skip=0, limit=10, sort_by="rank", search="catan"
        )
        end_time = time.time()
        logger.info(
            "Success: %d games in %.1fms",
            len(games),
            (end_time - start_time) * 1000,
        )

        # Test 3: Games with player filter
        logger.info("3. Testing games with player filter...")
        start_time = time.time()
        games, total = crud.get_games(db, skip=0, limit=10, sort_by="rank", players=4)
        end_time = time.time()
        logger.info(
            "Success: %d games in %.1fms",
            len(games),
            (end_time - start_time) * 1000,
        )

        # Test 4: Games with weight filter
        logger.info("4. Testing games with weight filter...")
        start_time = time.time()
        games, total = crud.get_games(
            db, skip=0, limit=10, sort_by="rank", weight="beginner"
        )
        end_time = time.time()
        logger.info(
            "Success: %d games in %.1fms",
            len(games),
            (end_time - start_time) * 1000,
        )

        # Test 5: Mechanics query
        logger.info("5. Testing mechanics query...")
        start_time = time.time()
        mechanics = crud.get_mechanics_cached(db, skip=0, limit=50)
        end_time = time.time()
        logger.info(
            "Success: %d mechanics in %.1fms",
            len(mechanics),
            (end_time - start_time) * 1000,
        )

        logger.info("All tests passed. Database queries are working correctly.")

    except Exception:
        logger.exception("Database query test failed")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    test_basic_queries()
