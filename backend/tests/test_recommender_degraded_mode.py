import json
import os

from scipy import sparse

from backend.app import recommender


def reset_model_manager():
    manager = recommender.ModelManager.get_instance()
    manager._game_embeddings = None
    manager._model_path = None
    manager._game_mapping = {}
    manager._reverse_game_mapping = {}
    manager._last_load_error = None
    return manager


def test_get_recommendations_returns_empty_when_embeddings_missing(
    monkeypatch, tmp_path
):
    manager = reset_model_manager()

    monkeypatch.setenv("DATABASE_DIR", str(tmp_path))

    result = recommender.get_recommendations(
        db=None,
        liked_games=[1],
    )

    assert result == []
    status = manager.get_status()
    assert status["available"] is False
    assert status["state"] == "degraded"
    assert status["detail"] == "No embeddings files found"


def test_load_model_uses_newest_matched_artifact_pair(monkeypatch, tmp_path):
    manager = reset_model_manager()

    old_embeddings = tmp_path / "game_embeddings_100.npz"
    new_embeddings = tmp_path / "game_embeddings_200.npz"
    unmatched_embeddings = tmp_path / "game_embeddings_300.npz"
    old_mapping = tmp_path / "reverse_mappings_100.json"
    new_mapping = tmp_path / "reverse_mappings_200.json"

    sparse.save_npz(old_embeddings, sparse.csr_matrix([[1.0, 0.0]]))
    sparse.save_npz(new_embeddings, sparse.csr_matrix([[0.0, 1.0]]))
    sparse.save_npz(unmatched_embeddings, sparse.csr_matrix([[1.0, 1.0]]))
    old_mapping.write_text(json.dumps({"0": 111}), encoding="utf-8")
    new_mapping.write_text(json.dumps({"0": 222}), encoding="utf-8")

    # Make mtimes misleading on purpose; filename timestamp should still win.
    os.utime(old_embeddings, (400, 400))
    os.utime(old_mapping, (400, 400))
    os.utime(new_embeddings, (100, 100))
    os.utime(new_mapping, (100, 100))
    os.utime(unmatched_embeddings, (500, 500))

    monkeypatch.setenv("DATABASE_DIR", str(tmp_path))

    manager.load_model()

    assert manager._model_path == new_embeddings
    assert manager._reverse_game_mapping == {0: 222}
    status = manager.get_status()
    assert status["available"] is True
    assert status["state"] == "available"
