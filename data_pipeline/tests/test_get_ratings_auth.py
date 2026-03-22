import pytest
import pandas as pd

from data_pipeline.src.ingest.get_ratings import (
    _http_get_bgg_xml,
    get_boardgame_ratings,
)


def test_http_get_bgg_xml_includes_bearer_token(monkeypatch):
    captured: dict[str, object] = {}

    class _Response:
        content = b"<items></items>"

        def raise_for_status(self):
            return None

    def _fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setenv("BGG_TOKEN", "ratings-token")
    monkeypatch.setattr(
        "data_pipeline.src.ingest.get_ratings.requests.get",
        _fake_get,
    )

    _http_get_bgg_xml("https://www.boardgamegeek.com/xmlapi2/thing?id=1")

    assert captured["headers"] == {"Authorization": "Bearer ratings-token"}


def test_http_get_bgg_xml_reads_token_from_repo_root_dotenv(monkeypatch):
    captured: dict[str, object] = {}

    class _Response:
        content = b"<items></items>"

        def raise_for_status(self):
            return None

    def _fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.delenv("BGG_TOKEN", raising=False)
    monkeypatch.setattr(
        "data_pipeline.src.ingest.get_ratings.Path.exists",
        lambda _self: True,
    )
    monkeypatch.setattr(
        "data_pipeline.src.ingest.get_ratings.load_dotenv",
        lambda *args, **kwargs: monkeypatch.setenv("BGG_TOKEN", "dotenv-token"),
    )
    monkeypatch.setattr(
        "data_pipeline.src.ingest.get_ratings.requests.get",
        _fake_get,
    )

    _http_get_bgg_xml("https://www.boardgamegeek.com/xmlapi2/thing?id=1")

    assert captured["headers"] == {"Authorization": "Bearer dotenv-token"}


def test_http_get_bgg_xml_raises_when_bgg_token_missing(monkeypatch):
    monkeypatch.setattr(
        "data_pipeline.src.ingest.get_ratings._get_bgg_token",
        lambda: "",
    )

    with pytest.raises(ValueError, match="Missing required BGG_TOKEN"):
        _http_get_bgg_xml("https://www.boardgamegeek.com/xmlapi2/thing?id=1")


def test_get_boardgame_ratings_closes_duckdb_connection_on_exception(
    monkeypatch, tmp_path
):
    class _FakeDuckDbConnection:
        def __init__(self):
            self.closed = False

        def execute(self, *_args, **_kwargs):
            return self

        def close(self):
            self.closed = True

    fake_connection = _FakeDuckDbConnection()
    monkeypatch.setattr(
        "data_pipeline.src.ingest.get_ratings.duckdb.connect",
        lambda *_args, **_kwargs: fake_connection,
    )
    monkeypatch.setattr(
        "data_pipeline.src.ingest.get_ratings.iterate_through_ratings_pages",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("forced failure")),
    )

    with pytest.raises(RuntimeError, match="forced failure"):
        get_boardgame_ratings(
            boardgame_data=pd.DataFrame([{"id": 1, "numratings": 150}]),
            ratings_store_path=tmp_path / "ratings.duckdb",
            batch_size=20,
        )

    assert fake_connection.closed is True
