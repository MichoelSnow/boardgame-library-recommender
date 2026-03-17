import pytest

from backend.app.main import _analyze_library_csv


def test_analyze_library_csv_accepts_header_and_dedicated_column():
    payload = b"name,bgg_id,publisher\nCatan,13,Foo\nAzul,230802,Bar\n"
    analyzed = _analyze_library_csv(payload)
    assert analyzed["total_rows"] == 2
    assert analyzed["deduped_rows"] == [(2, 13), (3, 230802)]
    assert analyzed["invalid_warnings"] == []


def test_analyze_library_csv_accepts_single_column_without_header():
    payload = b"13\n230802\n42\n"
    analyzed = _analyze_library_csv(payload)
    assert analyzed["deduped_rows"] == [(1, 13), (2, 230802), (3, 42)]


def test_analyze_library_csv_warns_and_continues_for_invalid_values():
    analyzed = _analyze_library_csv(b"bgg_id\nabc\n-5\n+3\n1.2\n0\n14\n")
    assert analyzed["deduped_rows"] == [(7, 14)]
    assert len(analyzed["invalid_warnings"]) == 5


def test_analyze_library_csv_rejects_empty_payload():
    with pytest.raises(ValueError, match="CSV file is empty"):
        _analyze_library_csv(b"")


def test_analyze_library_csv_preserves_multiline_quoted_field():
    analyzed = _analyze_library_csv(b'bgg_id\n"1\n3"\n42\n')

    assert analyzed["deduped_rows"] == [(3, 42)]
    assert analyzed["invalid_warnings"] == [
        {"row_number": 2, "value": "1\n3", "reason": "not_positive_integer"}
    ]
