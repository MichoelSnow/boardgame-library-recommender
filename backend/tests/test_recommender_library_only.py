from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from scipy import sparse

from backend.app import models, recommender


def _reset_model_manager() -> recommender.ModelManager:
    manager = recommender.ModelManager.get_instance()
    manager._game_embeddings = None
    manager._model_path = None
    manager._game_mapping = {}
    manager._reverse_game_mapping = {}
    manager._last_load_error = None
    return manager


def test_get_recommendations_library_only_filters_via_db_query() -> None:
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    db.add_all(
        [
            models.BoardGame(id=1, name="Liked Seed"),
            models.BoardGame(id=2, name="Non-Library Candidate"),
            models.BoardGame(id=3, name="Library Candidate"),
        ]
    )
    db.add(models.LibraryGame(name="Library Entry", bgg_id=3))
    db.commit()

    manager = _reset_model_manager()
    manager._game_embeddings = sparse.csr_matrix(
        [
            [1.0, 0.0],  # game 1 (liked seed)
            [0.95, 0.05],  # game 2 (higher score, non-Library)
            [0.90, 0.10],  # game 3 (slightly lower score, Library)
        ]
    )
    manager._game_mapping = {1: 0, 2: 1, 3: 2}
    manager._reverse_game_mapping = {0: 1, 1: 2, 2: 3}

    library_only_results = recommender.get_recommendations(
        db=db,
        limit=5,
        liked_games=[1],
        library_only=True,
    )
    all_results = recommender.get_recommendations(
        db=db,
        limit=5,
        liked_games=[1],
        library_only=False,
    )

    library_only_ids = [int(game["id"]) for game in library_only_results]
    all_ids = [int(game["id"]) for game in all_results]

    assert 2 in all_ids
    assert library_only_ids == [3]
