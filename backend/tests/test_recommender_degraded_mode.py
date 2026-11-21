from backend.app import recommender


def test_recommendations_degrade_when_embeddings_are_missing(monkeypatch, tmp_path):
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
    monkeypatch.setenv("DATABASE_DIR", str(tmp_path))

    assert recommender.get_recommendations(db=None, liked_games=[1]) == []
    assert manager.get_status()["state"] == "degraded"
