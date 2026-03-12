"""Player-count filter tests for catalog queries."""

import logging
import time

from backend.app import crud
from backend.app.database import SessionLocal

LOGGER = logging.getLogger(__name__)


def _assert_games_support_player_count(games, player_count: int) -> None:
    for game in games:
        if game.min_players is None or game.max_players is None:
            continue
        assert game.min_players <= player_count <= game.max_players, (
            f"Game '{game.name}' has min_players={game.min_players}, "
            f"max_players={game.max_players}, expected support for {player_count} players."
        )


def test_player_filter():
    """Verify games returned for selected player counts all support that count."""
    db = SessionLocal()

    try:
        # Test 1: Games that support 4 players
        start_time = time.time()
        games, _ = crud.get_games(db, skip=0, limit=5, sort_by="rank", players=4)
        end_time = time.time()
        LOGGER.info(
            "Found %d games supporting 4 players in %.1fms",
            len(games),
            (end_time - start_time) * 1000,
        )
        _assert_games_support_player_count(games, player_count=4)

        # Test 2: Games that support 2 players
        start_time = time.time()
        games, _ = crud.get_games(db, skip=0, limit=5, sort_by="rank", players=2)
        end_time = time.time()
        LOGGER.info(
            "Found %d games supporting 2 players in %.1fms",
            len(games),
            (end_time - start_time) * 1000,
        )
        _assert_games_support_player_count(games, player_count=2)

        # Test 3: Games that support 6 players
        start_time = time.time()
        games, _ = crud.get_games(db, skip=0, limit=5, sort_by="rank", players=6)
        end_time = time.time()
        LOGGER.info(
            "Found %d games supporting 6 players in %.1fms",
            len(games),
            (end_time - start_time) * 1000,
        )
        _assert_games_support_player_count(games, player_count=6)
    finally:
        db.close()


if __name__ == "__main__":
    test_player_filter()
