from scripts.perf.profile_hot_endpoints import (
    parse_endpoint,
    percentile,
    summarize_runs,
)


def test_parse_endpoint_defaults_to_200() -> None:
    endpoint = parse_endpoint("GET /api/games/?limit=24")
    assert endpoint.method == "GET"
    assert endpoint.path == "/api/games/?limit=24"
    assert endpoint.expected_status == 200


def test_parse_endpoint_with_status_prefix() -> None:
    endpoint = parse_endpoint("401:GET /api/admin/users")
    assert endpoint.method == "GET"
    assert endpoint.path == "/api/admin/users"
    assert endpoint.expected_status == 401


def test_percentile_handles_empty_and_bounds() -> None:
    assert percentile([], 0.95) == 0.0
    assert percentile([5.0, 10.0, 15.0], 0.0) == 5.0
    assert percentile([5.0, 10.0, 15.0], 1.0) == 15.0


def test_summarize_runs_basic_shape() -> None:
    summary = summarize_runs(
        [
            {
                "ok": True,
                "status_code": 200,
                "response_ms": 100.0,
                "sql_count": 5,
                "sql_time_ms": 20.0,
                "sql_entries": [],
            },
            {
                "ok": False,
                "status_code": 500,
                "response_ms": 120.0,
                "sql_count": 6,
                "sql_time_ms": 30.0,
                "sql_entries": [],
            },
        ]
    )
    assert summary["iterations"] == 2
    assert summary["failures"] == 1
    assert summary["sql_count"]["max"] == 6
