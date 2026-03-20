import duckdb
import pandas as pd
import pytest

from data_pipeline.src.ingest.get_game_data import (
    _initialize_game_data_store,
    _load_completed_ids,
    _load_game_data_from_store,
    _http_get_bgg_xml,
    get_boardgame_data,
    _upsert_game_batch,
)


def test_duckdb_store_upsert_and_reload(tmp_path):
    db_path = tmp_path / "boardgame_data_123.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        _initialize_game_data_store(con)

        first_batch = [
            {"id": 1, "name": "Game One", "numratings": 10},
            {"id": 2, "name": "Game Two", "numratings": 20},
        ]
        _upsert_game_batch(con, first_batch)
        assert _load_completed_ids(con) == {1, 2}

        second_batch = [
            {"id": 2, "name": "Game Two Updated", "numratings": 25},
            {"id": 3, "name": "Game Three", "numratings": 30},
        ]
        _upsert_game_batch(con, second_batch)

        loaded_df = _load_game_data_from_store(con)
        assert set(loaded_df["id"].tolist()) == {1, 2, 3}
        updated_name = loaded_df.loc[loaded_df["id"] == 2, "name"].iloc[0]
        assert updated_name == "Game Two Updated"
    finally:
        con.close()


def test_get_game_data_raises_if_batch_returns_no_items(tmp_path, monkeypatch):
    class _Response:
        content = b"<items></items>"

    monkeypatch.setattr(
        "data_pipeline.src.ingest.get_game_data._http_get_bgg_xml",
        lambda _url: _Response(),
    )
    monkeypatch.setattr(
        "data_pipeline.src.ingest.get_game_data.sleep",
        lambda _seconds: None,
    )

    ranks_df = pd.DataFrame({"id": [1, 2]})
    store_path = tmp_path / "boardgame_data_123.duckdb"

    with pytest.raises(RuntimeError, match="BGG API returned zero items for batch URL"):
        get_boardgame_data(
            boardgame_ranks=ranks_df,
            existing_store_path=store_path,
            batch_saves=True,
            batch_size=20,
            save_every_n_batches=1,
        )


def test_http_get_bgg_xml_includes_bearer_token(monkeypatch):
    captured: dict[str, object] = {}

    class _Response:
        def raise_for_status(self):
            return None

    def _fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setenv("BGG_TOKEN", "test-token")
    monkeypatch.setattr(
        "data_pipeline.src.ingest.get_game_data.requests.get",
        _fake_get,
    )

    _http_get_bgg_xml("https://boardgamegeek.com/xmlapi2/thing?id=1")

    assert captured["headers"] == {"Authorization": "Bearer test-token"}


def test_http_get_bgg_xml_reads_token_from_repo_root_dotenv(monkeypatch):
    captured: dict[str, object] = {}

    class _Response:
        def raise_for_status(self):
            return None

    def _fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.delenv("BGG_TOKEN", raising=False)
    monkeypatch.setattr(
        "data_pipeline.src.ingest.get_game_data.Path.exists",
        lambda _self: True,
    )
    monkeypatch.setattr(
        "data_pipeline.src.ingest.get_game_data.load_dotenv",
        lambda *args, **kwargs: monkeypatch.setenv("BGG_TOKEN", "dotenv-token"),
    )
    monkeypatch.setattr(
        "data_pipeline.src.ingest.get_game_data.requests.get",
        _fake_get,
    )

    _http_get_bgg_xml("https://boardgamegeek.com/xmlapi2/thing?id=1")

    assert captured["headers"] == {"Authorization": "Bearer dotenv-token"}


def test_http_get_bgg_xml_raises_when_bgg_token_missing(monkeypatch):
    monkeypatch.setattr(
        "data_pipeline.src.ingest.get_game_data._get_bgg_token",
        lambda: "",
    )

    with pytest.raises(ValueError, match="Missing required BGG_TOKEN"):
        _http_get_bgg_xml("https://boardgamegeek.com/xmlapi2/thing?id=1")
