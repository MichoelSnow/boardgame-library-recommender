from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import pytest

from data_pipeline.src.ingest import get_ranks


def _build_ranks_zip_bytes(csv_text: str) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, mode="w") as archive:
        archive.writestr(get_ranks.RANKS_CSV_FILENAME, csv_text)
    return buffer.getvalue()


def test_load_ranks_dataframe_adds_timestamp_and_normalizes_name() -> None:
    queried_at_utc = "2026-03-13T15:00:00+00:00"
    zip_bytes = _build_ranks_zip_bytes("id,name\n1,Test “Name”\n")
    df = get_ranks._load_ranks_dataframe(zip_bytes, queried_at_utc)

    assert list(df.columns) == ["id", "name", "queried_at_utc"]
    assert len(df) == 1
    assert int(df.iloc[0]["id"]) == 1
    assert df.iloc[0]["name"] == 'Test "Name"'
    assert df.iloc[0]["queried_at_utc"] == queried_at_utc


def test_load_ranks_dataframe_raises_when_csv_missing() -> None:
    queried_at_utc = "2026-03-13T15:00:00+00:00"
    buffer = BytesIO()
    with ZipFile(buffer, mode="w") as archive:
        archive.writestr("other.csv", "id,name\n1,Missing\n")

    with pytest.raises(ValueError, match="Expected boardgames_ranks.csv"):
        get_ranks._load_ranks_dataframe(buffer.getvalue(), queried_at_utc)


def test_load_ranks_dataframe_raises_when_required_columns_missing() -> None:
    queried_at_utc = "2026-03-13T15:00:00+00:00"
    zip_bytes = _build_ranks_zip_bytes("name\nNo ID Column\n")

    with pytest.raises(ValueError, match="missing required columns: id"):
        get_ranks._load_ranks_dataframe(zip_bytes, queried_at_utc)


def test_save_ranks_dataframe_writes_expected_pipe_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    queried_at_utc = "2026-03-13T15:00:00+00:00"
    df = pd.DataFrame(
        [{"id": 1, "name": 'Test "Name"', "queried_at_utc": queried_at_utc}]
    )

    ingest_file = (
        tmp_path / "repo" / "data_pipeline" / "src" / "ingest" / "get_ranks.py"
    )
    ingest_file.parent.mkdir(parents=True, exist_ok=True)
    ingest_file.write_text("# test", encoding="utf-8")
    monkeypatch.setattr(get_ranks, "__file__", str(ingest_file))

    output_file = get_ranks._save_ranks_dataframe(df, queried_at_utc)
    assert output_file.name == "boardgame_ranks_20260313.csv"
    assert output_file.exists()


def test_get_boardgame_ranks_requires_direct_url() -> None:
    with pytest.raises(ValueError, match="ranks_zip_url is required"):
        get_ranks.get_boardgame_ranks(ranks_zip_url="", save_file=False)


def test_get_boardgame_ranks_uses_direct_zip_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queried_zip = _build_ranks_zip_bytes("id,name\n1,Direct Link Game\n")

    class _Resp:
        def __init__(self, content: bytes):
            self.content = content

        def raise_for_status(self) -> None:
            return None

    calls: list[str] = []

    def _mock_http_get(url: str):
        calls.append(url)
        return _Resp(queried_zip)

    monkeypatch.setattr(get_ranks, "_http_get", _mock_http_get)
    df = get_ranks.get_boardgame_ranks(
        ranks_zip_url="https://example.com/direct.zip",
        save_file=False,
    )
    assert len(df) == 1
    assert int(df.iloc[0]["id"]) == 1
    assert df.iloc[0]["name"] == "Direct Link Game"
    assert calls == ["https://example.com/direct.zip"]
