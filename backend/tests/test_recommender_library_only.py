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
    manager._content_embeddings = None
    manager._content_model_path = None
    manager._content_game_mapping = {}
    manager._content_reverse_game_mapping = {}
    manager._last_load_error = None
    manager._last_content_load_error = None
    return manager


def test_get_recommendations_library_only_prefers_active_import() -> None:
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
    db.flush()
    active_import = models.LibraryImport(
        label="active_import",
        import_method="csv_upload",
        is_active=True,
    )
    db.add(active_import)
    db.flush()
    db.add(
        models.LibraryImportItem(
            library_import_id=active_import.id,
            bgg_id=3,
        )
    )
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


def test_get_recommendations_library_only_requires_active_import() -> None:
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    db.add_all(
        [
            models.BoardGame(id=1, name="Liked Seed"),
            models.BoardGame(id=2, name="Candidate"),
            models.BoardGame(id=3, name="Non-Library Candidate"),
        ]
    )
    db.commit()

    manager = _reset_model_manager()
    manager._game_embeddings = sparse.csr_matrix(
        [
            [1.0, 0.0],
            [0.95, 0.05],
            [0.90, 0.10],
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

    library_only_ids = [int(game["id"]) for game in library_only_results]
    assert library_only_ids == []
