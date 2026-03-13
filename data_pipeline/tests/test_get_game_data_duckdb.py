import duckdb
import pandas as pd
import pytest

from data_pipeline.src.ingest.get_game_data import (
    _initialize_game_data_store,
    _load_completed_ids,
    _load_game_data_from_store,
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
        "data_pipeline.src.ingest.get_game_data.requests.get",
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
