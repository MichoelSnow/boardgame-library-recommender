import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import crud, models


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    games = [
        models.BoardGame(
            id=1,
            name="Alpha",
            min_players=1,
            max_players=8,
            max_playtime=30,
            min_age=8,
            average_weight=1.5,
            rank=1,
            family_games_rank=1,
        ),
        models.BoardGame(
            id=2,
            name="Beta",
            min_players=1,
            max_players=12,
            max_playtime=60,
            min_age=10,
            average_weight=3.0,
            rank=2,
            party_games_rank=2,
        ),
        models.BoardGame(
            id=3,
            name="Gamma",
            min_players=1,
            max_players=10,
            max_playtime=45,
            min_age=12,
            average_weight=4.5,
            rank=3,
        ),
        models.BoardGame(
            id=4,
            name="Delta",
            min_players=1,
            max_players=6,
            max_playtime=0,
            min_age=8,
            average_weight=2.0,
            rank=4,
        ),
    ]
    games[0].mechanics = [
        models.Mechanic(
            boardgamemechanic_id=1, boardgamemechanic_name="Cooperative Game"
        ),
        models.Mechanic(boardgamemechanic_id=2, boardgamemechanic_name="Deduction"),
        models.Mechanic(
            boardgamemechanic_id=3002, boardgamemechanic_name="Deduction Mechanic"
        ),
        models.Mechanic(boardgamemechanic_id=3113, boardgamemechanic_name="Spelling"),
    ]
    games[1].mechanics = [
        models.Mechanic(boardgamemechanic_id=2, boardgamemechanic_name="Deduction"),
    ]
    games[2].mechanics = [
        models.Mechanic(
            boardgamemechanic_id=1, boardgamemechanic_name="Cooperative Game"
        ),
        models.Mechanic(
            boardgamemechanic_id=2072, boardgamemechanic_name="Dice Rolling"
        ),
    ]
    games[3].mechanics = [
        models.Mechanic(boardgamemechanic_id=2876, boardgamemechanic_name="Race"),
    ]
    games[0].categories = [
        models.Category(boardgamecategory_id=7, boardgamecategory_name="Party Game"),
    ]
    games[1].categories = [
        models.Category(boardgamecategory_id=8, boardgamecategory_name="Fantasy"),
        models.Category(boardgamecategory_id=1031, boardgamecategory_name="Racing"),
    ]
    games[2].categories = [
        models.Category(
            boardgamecategory_id=9, boardgamecategory_name="Children's Game"
        ),
        models.Category(boardgamecategory_id=1010, boardgamecategory_name="Fantasy"),
    ]
    games[3].categories = [
        models.Category(boardgamecategory_id=8, boardgamecategory_name="Fantasy"),
    ]
    games[2].suggested_players = [
        models.SuggestedPlayer(
            player_count=9,
            recommendation_level="best",
        ),
        models.SuggestedPlayer(
            player_count=10,
            recommendation_level="recommended",
        ),
    ]
    games[1].suggested_players = [
        models.SuggestedPlayer(
            player_count=9,
            recommendation_level="not_recommended",
        ),
    ]
    session.add_all(games)
    session.commit()

    try:
        yield session
    finally:
        session.close()
        models.Base.metadata.drop_all(engine)
        engine.dispose()


def _game_ids(result):
    games, total = result
    return [game.id for game in games], total


def test_expanded_game_filters_use_or_within_groups_and_and_across_groups(db_session):
    mechanics_ids, _ = _game_ids(crud.get_games(db_session, limit=20, mechanics="1,2"))
    categories_ids, _ = _game_ids(
        crud.get_games(db_session, limit=20, categories="7,8")
    )
    combined_ids, _ = _game_ids(
        crud.get_games(
            db_session,
            limit=20,
            mechanics="1,2",
            categories="7,8",
            cooperative=True,
        )
    )

    assert mechanics_ids == [1, 2, 3]
    assert categories_ids == [1, 2, 4]
    assert combined_ids == [1]

    assert _game_ids(crud.get_games(db_session, limit=20, game_style="family"))[0] == [
        1
    ]
    assert _game_ids(crud.get_games(db_session, limit=20, game_style="children"))[
        0
    ] == [3]
    assert _game_ids(crud.get_games(db_session, limit=20, game_style="party"))[0] == [
        1,
        2,
    ]

    age_and_time_ids, _ = _game_ids(
        crud.get_games(db_session, limit=20, max_playtime=45, min_age=10)
    )
    assert age_and_time_ids == [1]


def test_nine_plus_recommendations_pagination_and_cache_keys(db_session):
    allowed_ids, allowed_total = _game_ids(
        crud.get_games(db_session, limit=1, players="9plus")
    )
    recommended_ids, _ = _game_ids(
        crud.get_games(
            db_session,
            limit=20,
            players="9plus",
            recommendations="recommended",
        )
    )
    best_ids, _ = _game_ids(
        crud.get_games(
            db_session,
            limit=20,
            players="9plus",
            recommendations="best",
        )
    )

    assert allowed_ids == [2]
    assert allowed_total == 2
    assert recommended_ids == [3]
    assert best_ids == [3]

    key_args = {
        "search": None,
        "players": None,
        "designer_id": None,
        "artist_id": None,
        "recommendations": None,
        "weight": None,
        "mechanics": None,
        "categories": None,
        "max_playtime": None,
        "min_age": None,
        "game_style": None,
        "cooperative": None,
        "library_only": False,
    }
    base_key = crud._build_total_cache_key(**key_args)
    assert base_key != crud._build_total_cache_key(**{**key_args, "max_playtime": 60})
    assert base_key != crud._build_total_cache_key(**{**key_args, "cooperative": True})


def test_taxonomy_filters_expand_merged_sources_and_preserve_distinct_options(
    db_session,
):
    deduction_ids, _ = _game_ids(
        crud.get_games(db_session, limit=20, game_types="game-type:deduction")
    )
    word_ids, _ = _game_ids(
        crud.get_games(db_session, limit=20, game_types="game-type:word-games")
    )
    dice_ids, _ = _game_ids(
        crud.get_games(db_session, limit=20, game_types="game-type:dice-games")
    )
    merged_ids, _ = _game_ids(
        crud.get_games(
            db_session,
            limit=20,
            game_types="game-type:deduction,game-type:dice-games",
        )
    )
    racing_ids, _ = _game_ids(
        crud.get_games(db_session, limit=20, game_types="game-type:racing")
    )
    race_mechanic_ids, _ = _game_ids(
        crud.get_games(db_session, limit=20, game_types="game-type:race-mechanic")
    )
    unknown_ids, _ = _game_ids(
        crud.get_games(db_session, limit=20, game_types="game-type:does-not-exist")
    )

    assert deduction_ids == [1]
    assert word_ids == [1]
    assert dice_ids == [3]
    assert merged_ids == [1, 3]
    assert racing_ids == [2]
    assert race_mechanic_ids == [4]
    assert unknown_ids == [1, 2, 3, 4]
