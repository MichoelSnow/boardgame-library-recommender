import pandas as pd

from backend.app.import_library_data import _extract_unique_bgg_ids, _parse_bgg_id


def test_parse_bgg_id_accepts_positive_numeric_values() -> None:
    assert _parse_bgg_id("10") == 10
    assert _parse_bgg_id("10.0") == 10
    assert _parse_bgg_id(15) == 15


def test_parse_bgg_id_rejects_invalid_or_non_positive_values() -> None:
    assert _parse_bgg_id(None) is None
    assert _parse_bgg_id("") is None
    assert _parse_bgg_id("abc") is None
    assert _parse_bgg_id("0") is None
    assert _parse_bgg_id("-5") is None


def test_extract_unique_bgg_ids_dedupes_and_counts_invalid_rows() -> None:
    frame = pd.DataFrame(
        {
            "bgg_id": ["1", "2", "2", "", None, "abc", "3.0", "0", "-1"],
        }
    )

    ids, invalid_count, duplicate_count = _extract_unique_bgg_ids(frame)

    assert ids == [1, 2, 3]
    assert invalid_count == 5
    assert duplicate_count == 1
