from backend.app import recommender


def test_get_recommendations_returns_empty_when_embeddings_missing(monkeypatch, tmp_path):
    manager = recommender.ModelManager.get_instance()
    manager._game_embeddings = None
    manager._model_path = None
    manager._game_mapping = {}
    manager._reverse_game_mapping = {}

    monkeypatch.setenv("DATABASE_DIR", str(tmp_path))

    result = recommender.get_recommendations(
        db=None,
        liked_games=[1],
    )

    assert result == []
