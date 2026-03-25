from scipy import sparse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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


def test_recommendation_mode_switch_changes_scores() -> None:
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    db.add_all(
        [
            models.BoardGame(
                id=1,
                name="Liked Seed",
                bayes_average=7.0,
                average=7.0,
                num_ratings=1000,
            ),
            models.BoardGame(
                id=2,
                name="Collaborative Favorite",
                bayes_average=7.0,
                average=7.0,
                num_ratings=1000,
            ),
            models.BoardGame(
                id=3,
                name="Content Match Favorite",
                bayes_average=7.0,
                average=7.0,
                num_ratings=1000,
            ),
        ]
    )
    db.commit()

    manager = _reset_model_manager()
    manager._game_embeddings = sparse.csr_matrix(
        [
            [1.0, 0.0],  # game 1 (liked)
            [0.98, 0.02],  # game 2 (slightly higher collaborative similarity)
            [0.95, 0.05],  # game 3 (slightly lower collaborative similarity)
        ]
    )
    manager._game_mapping = {1: 0, 2: 1, 3: 2}
    manager._reverse_game_mapping = {0: 1, 1: 2, 2: 3}
    manager._content_embeddings = sparse.csr_matrix(
        [
            [1.0, 0.0],  # game 1 (liked)
            [0.10, 0.99],  # game 2 (low content similarity)
            [0.95, 0.05],  # game 3 (high content similarity)
        ]
    )
    manager._content_game_mapping = {1: 0, 2: 1, 3: 2}
    manager._content_reverse_game_mapping = {0: 1, 1: 2, 2: 3}

    collaborative_results = recommender.get_recommendations(
        db=db,
        limit=2,
        liked_games=[1],
        recommender_mode="collaborative",
    )
    hybrid_results = recommender.get_recommendations(
        db=db,
        limit=2,
        liked_games=[1],
        recommender_mode="hybrid",
    )

    collaborative_scores = {
        int(item["id"]): float(item["recommendation_score"])
        for item in collaborative_results
    }
    hybrid_scores = {
        int(item["id"]): float(item["recommendation_score"]) for item in hybrid_results
    }

    assert 2 in collaborative_scores
    assert 3 in collaborative_scores
    assert 2 in hybrid_scores
    assert 3 in hybrid_scores
    assert all(0.0 <= score <= 1.0 for score in hybrid_scores.values())
    assert any(
        abs(collaborative_scores[game_id] - hybrid_scores[game_id]) > 1e-9
        for game_id in (2, 3)
    )
