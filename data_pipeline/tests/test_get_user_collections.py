import logging
from pathlib import Path

import duckdb
import requests

from data_pipeline.src.ingest import get_user_collections


def _response(status_code: int, content: bytes, headers: dict[str, str] | None = None):
    response = requests.Response()
    response.status_code = status_code
    response._content = content
    response.headers.update(headers or {})
    return response


def test_populate_selected_users_counts_each_rating_row(tmp_path: Path):
    ratings_path = tmp_path / "ratings.duckdb"
    ratings_connection = duckdb.connect(str(ratings_path))
    ratings_connection.execute(
        "CREATE TABLE boardgame_ratings (game_id BIGINT, rating_round DOUBLE, username TEXT)"
    )
    ratings_connection.executemany(
        "INSERT INTO boardgame_ratings VALUES (?, ?, ?)",
        [
            (1, 8.0, "alice"),
            (1, 8.0, "alice"),
            (2, 7.0, "alice"),
            (3, 9.0, "bob"),
            (4, 6.0, "carol"),
        ],
    )
    ratings_connection.close()

    collections_connection = duckdb.connect(str(tmp_path / "collections.duckdb"))
    get_user_collections._initialize_collection_store(collections_connection)
    selected_count = get_user_collections._populate_selected_users(
        collections_connection,
        ratings_path,
        coverage_percent=75,
        max_users=None,
    )

    assert selected_count == 2
    assert collections_connection.execute(
        """
        SELECT username, rating_count, selection_rank, cumulative_rating_count,
               total_rating_count, coverage_percent
        FROM collection_users
        ORDER BY selection_rank
        """
    ).fetchall() == [
        ("alice", 3, 1, 3, 5, 60.0),
        ("bob", 1, 2, 4, 5, 80.0),
    ]
    collections_connection.close()


def test_populate_selected_users_appends_additional_ranked_users(tmp_path: Path):
    ratings_path = tmp_path / "ratings.duckdb"
    ratings_connection = duckdb.connect(str(ratings_path))
    ratings_connection.execute(
        "CREATE TABLE boardgame_ratings (game_id BIGINT, rating_round DOUBLE, username TEXT)"
    )
    ratings_connection.executemany(
        "INSERT INTO boardgame_ratings VALUES (?, ?, ?)",
        [
            (1, 8.0, "alice"),
            (2, 8.0, "alice"),
            (3, 8.0, "alice"),
            (4, 7.0, "bob"),
            (5, 7.0, "bob"),
            (6, 6.0, "carol"),
        ],
    )
    ratings_connection.close()

    collections_connection = duckdb.connect(str(tmp_path / "collections.duckdb"))
    get_user_collections._initialize_collection_store(collections_connection)

    assert (
        get_user_collections._populate_selected_users(
            collections_connection,
            ratings_path,
            coverage_percent=None,
            max_users=None,
            additional_users=1,
            existing_user_count=0,
        )
        == 1
    )
    assert (
        get_user_collections._populate_selected_users(
            collections_connection,
            ratings_path,
            coverage_percent=None,
            max_users=None,
            additional_users=1,
            existing_user_count=1,
        )
        == 2
    )

    assert collections_connection.execute(
        "SELECT username, selection_rank FROM collection_users ORDER BY selection_rank"
    ).fetchall() == [("alice", 1), ("bob", 2)]
    collections_connection.close()


def test_populate_selected_users_fills_max_users_target(tmp_path: Path):
    ratings_path = tmp_path / "ratings.duckdb"
    ratings_connection = duckdb.connect(str(ratings_path))
    ratings_connection.execute(
        "CREATE TABLE boardgame_ratings (game_id BIGINT, rating_round DOUBLE, username TEXT)"
    )
    ratings_connection.executemany(
        "INSERT INTO boardgame_ratings VALUES (?, ?, ?)",
        [(1, 8.0, "alice"), (2, 7.0, "bob"), (3, 6.0, "carol")],
    )
    ratings_connection.close()

    collections_connection = duckdb.connect(str(tmp_path / "collections.duckdb"))
    get_user_collections._initialize_collection_store(collections_connection)

    assert (
        get_user_collections._populate_selected_users(
            collections_connection,
            ratings_path,
            coverage_percent=None,
            max_users=1,
            existing_user_count=0,
        )
        == 1
    )
    assert (
        get_user_collections._populate_selected_users(
            collections_connection,
            ratings_path,
            coverage_percent=None,
            max_users=3,
            existing_user_count=1,
        )
        == 3
    )
    assert collections_connection.execute(
        "SELECT username, selection_rank FROM collection_users ORDER BY selection_rank"
    ).fetchall() == [("alice", 1), ("bob", 2), ("carol", 3)]
    collections_connection.close()


def test_find_or_create_store_max_users_target_is_idempotent(tmp_path: Path):
    ratings_path = tmp_path / "ratings.duckdb"
    ratings_connection = duckdb.connect(str(ratings_path))
    ratings_connection.execute(
        "CREATE TABLE boardgame_ratings (game_id BIGINT, rating_round DOUBLE, username TEXT)"
    )
    ratings_connection.executemany(
        "INSERT INTO boardgame_ratings VALUES (?, ?, ?)",
        [(1, 8.0, "alice"), (2, 7.0, "bob"), (3, 6.0, "carol")],
    )
    ratings_connection.close()
    collections_dir = tmp_path / "collections"

    store_path, connection = get_user_collections._find_or_create_store(
        collections_dir,
        ratings_path,
        continue_from_last=False,
        coverage_percent=None,
        max_users=1,
        additional_users=None,
        selection_mode="max_users",
        selection_value=1,
    )
    connection.close()

    resumed_path, connection = get_user_collections._find_or_create_store(
        collections_dir,
        ratings_path,
        continue_from_last=True,
        coverage_percent=None,
        max_users=3,
        additional_users=None,
        selection_mode="max_users",
        selection_value=3,
    )
    assert resumed_path == store_path
    assert connection.execute("SELECT COUNT(*) FROM collection_users").fetchone() == (
        3,
    )
    connection.close()

    _, connection = get_user_collections._find_or_create_store(
        collections_dir,
        ratings_path,
        continue_from_last=True,
        coverage_percent=None,
        max_users=3,
        additional_users=None,
        selection_mode="max_users",
        selection_value=3,
    )
    assert connection.execute("SELECT COUNT(*) FROM collection_users").fetchone() == (
        3,
    )
    connection.close()


def test_parse_collection_items_extracts_user_level_fields():
    content = b"""<?xml version='1.0'?>
    <items username='alice' totalitems='1'>
      <item objecttype='thing' objectid='224517' subtype='boardgame' collid='42'>
        <name type='primary'>Brass: Birmingham</name>
        <originalname>Brass: Birmingham</originalname>
        <yearpublished>2018</yearpublished>
        <status own='1' prevowned='0' fortrade='0' want='0' wanttoplay='1'
          wanttobuy='0' wishlist='1' wishlistpriority='3' preordered='0'
          lastmodified='2026-11-01 12:00:00'/>
        <numplays>12</numplays>
        <stats><rating value='6.75'/></stats>
        <comment>Great game</comment>
        <conditiontext>Like New</conditiontext>
      </item>
    </items>"""

    result = get_user_collections._parse_collection_items(content, "alice")

    assert result.kind == "ready"
    assert result.items == [
        {
            "username": "alice",
            "game_id": 224517,
            "collection_id": 42,
            "object_type": "thing",
            "subtype": "boardgame",
            "name": "Brass: Birmingham",
            "original_name": "Brass: Birmingham",
            "year_published": 2018,
            "own": 1,
            "previously_owned": 0,
            "for_trade": 0,
            "want": 0,
            "want_to_play": 1,
            "want_to_buy": 0,
            "wishlist": 1,
            "wishlist_priority": 3,
            "preordered": 0,
            "last_modified": "2026-11-01 12:00:00",
            "num_plays": 12,
            "rating": 6.75,
            "comment": "Great game",
            "condition_text": "Like New",
        }
    ]


def test_process_batch_requeues_pending_users_and_saves_ready_items(
    tmp_path: Path, monkeypatch
):
    connection = duckdb.connect(str(tmp_path / "collections.duckdb"))
    get_user_collections._initialize_collection_store(connection)
    connection.execute(
        """
        INSERT INTO collection_users (
            username, rating_count, selection_rank, cumulative_rating_count,
            total_rating_count, coverage_percent, status, updated_at
        ) VALUES ('alice', 1, 1, 1, 1, 100, 'pending', 'now')
        """
    )
    monkeypatch.setattr(get_user_collections, "MIN_REQUEST_INTERVAL_SECONDS", 0)
    responses = iter(
        [
            _response(
                202,
                b"<message>Your request has been accepted and will be processed.</message>",
            ),
            _response(
                200,
                b"""
                <items>
                  <item objectid='224517' collid='42'><status own='1'/></item>
                  <item objectid='224517' collid='43'><status own='0'/></item>
                  <item objectid='224517' collid='42'><status own='1'/></item>
                </items>
                """,
            ),
        ]
    )

    failed = get_user_collections._process_batch(
        connection,
        get_user_collections._load_collection_user_batch(connection, 100),
        sleep_fn=lambda _seconds: None,
        monotonic_fn=lambda: 0,
        request_fn=lambda _username: next(responses),
    )

    assert failed == 0
    assert connection.execute(
        "SELECT status, attempts FROM collection_users WHERE username = 'alice'"
    ).fetchone() == ("complete", 2)
    assert connection.execute(
        """
        SELECT username, game_id, collection_id, own
        FROM user_collection_items
        ORDER BY collection_id
        """
    ).fetchall() == [
        ("alice", 224517, 42, 1),
        ("alice", 224517, 42, 1),
        ("alice", 224517, 43, 0),
    ]
    connection.close()


def test_process_batch_logs_compact_progress_counts(tmp_path: Path, caplog):
    connection = duckdb.connect(str(tmp_path / "collections.duckdb"))
    get_user_collections._initialize_collection_store(connection)
    connection.executemany(
        """
        INSERT INTO collection_users (
            username, rating_count, selection_rank, cumulative_rating_count,
            total_rating_count, coverage_percent, status, updated_at
        ) VALUES (?, 1, ?, ?, 5, 100, ?, 'now')
        """,
        [
            ("alice", 1, 1, "pending"),
            ("bob", 2, 2, "pending"),
            ("carol", 3, 3, "queued"),
            ("dave", 4, 4, "complete"),
            ("eve", 5, 5, "too_large"),
        ],
    )
    responses = iter(
        [
            _response(200, b"<items><item objectid='1'/></items>"),
            _response(
                202,
                b"<message>Your request has been accepted and will be processed.</message>",
            ),
            _response(
                200,
                b"<message>Collection exceeds maximum export size</message>",
            ),
            _response(200, b"<items><item objectid='2'/></items>"),
        ]
    )

    caplog.set_level(logging.INFO, logger=get_user_collections.logger.name)
    get_user_collections._process_batch(
        connection,
        [
            {
                "username": username,
                "selection_rank": rank,
                "status": status,
                "attempts": 0,
            }
            for username, rank, status in [
                ("alice", 1, "pending"),
                ("bob", 2, "pending"),
                ("carol", 3, "queued"),
                ("dave", 4, "complete"),
                ("eve", 5, "too_large"),
            ]
        ],
        sleep_fn=lambda _seconds: None,
        monotonic_fn=lambda: 0,
        request_fn=lambda _username: next(responses),
    )

    progress_lines = [
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("total=")
    ]
    assert progress_lines == [
        "total=5 complete=2 failed=1 retry_queued=1",
        "total=5 complete=2 failed=1 retry_queued=2",
        "total=5 complete=2 failed=2 retry_queued=1",
        "total=5 complete=3 failed=2 retry_queued=0",
    ]
    connection.close()


def test_classify_response_handles_bgg_pending_and_oversized_messages():
    pending = get_user_collections._classify_response(
        _response(
            202,
            b"<message>Your request has been accepted and will be processed.</message>",
        ),
        "alice",
    )
    too_large = get_user_collections._classify_response(
        _response(200, b"<message>Collection exceeds maximum export size</message>"),
        "alice",
    )
    invalid_user = get_user_collections._classify_response(
        _response(200, b"<message>Invalid username specified</message>"),
        "alice",
    )

    assert pending.kind == "pending"
    assert too_large.kind == "too_large"
    assert invalid_user.kind == "invalid_user"


def test_process_batch_marks_invalid_user_terminal_and_does_not_retry(
    tmp_path: Path,
):
    connection = duckdb.connect(str(tmp_path / "collections.duckdb"))
    get_user_collections._initialize_collection_store(connection)
    connection.execute(
        """
        INSERT INTO collection_users (
            username, rating_count, selection_rank, cumulative_rating_count,
            total_rating_count, coverage_percent, status, updated_at
        ) VALUES ('invalid', 1, 1, 1, 1, 100, 'pending', 'now')
        """
    )

    failed = get_user_collections._process_batch(
        connection,
        get_user_collections._load_collection_user_batch(connection, 100),
        sleep_fn=lambda _seconds: None,
        monotonic_fn=lambda: 0,
        request_fn=lambda _username: _response(
            200, b"<message>Invalid username specified</message>"
        ),
    )

    assert failed == 0
    assert connection.execute(
        "SELECT status, last_error FROM collection_users WHERE username = 'invalid'"
    ).fetchone() == ("invalid_user", "Invalid username specified")
    assert get_user_collections._load_collection_user_batch(connection, 100) == []
    connection.close()


def test_reset_failed_users_does_not_reset_invalid_users(tmp_path: Path):
    connection = duckdb.connect(str(tmp_path / "collections.duckdb"))
    get_user_collections._initialize_collection_store(connection)
    connection.executemany(
        """
        INSERT INTO collection_users (
            username, rating_count, selection_rank, cumulative_rating_count,
            total_rating_count, coverage_percent, status, updated_at
        ) VALUES (?, 1, ?, ?, 2, 100, ?, 'now')
        """,
        [("invalid", 1, 1, "invalid_user"), ("retryable", 2, 2, "failed")],
    )

    get_user_collections._reset_failed_users(connection)

    assert connection.execute(
        "SELECT username, status FROM collection_users ORDER BY selection_rank"
    ).fetchall() == [("invalid", "invalid_user"), ("retryable", "pending")]
    connection.close()


def test_classify_response_uses_retry_after_for_rate_limits():
    rate_limited = get_user_collections._classify_response(
        _response(
            429,
            b"<error><message>Rate limit exceeded.</message></error>",
            headers={"Retry-After": "45"},
        ),
        "alice",
    )

    assert rate_limited.kind == "transient"
    assert rate_limited.retry_after_seconds == 45.0


def test_429_applies_global_cooldown_before_next_request(tmp_path: Path, monkeypatch):
    connection = duckdb.connect(str(tmp_path / "collections.duckdb"))
    get_user_collections._initialize_collection_store(connection)
    connection.executemany(
        """
        INSERT INTO collection_users (
            username, rating_count, selection_rank, cumulative_rating_count,
            total_rating_count, coverage_percent, status, updated_at
        ) VALUES (?, 1, ?, ?, 2, 100, 'pending', 'now')
        """,
        [("alice", 1, 1), ("bob", 2, 2)],
    )
    monkeypatch.setattr(get_user_collections, "MIN_REQUEST_INTERVAL_SECONDS", 0)

    clock = [0.0]
    sleeps: list[float] = []

    def monotonic() -> float:
        return clock[0]

    def sleep_for(seconds: float) -> None:
        sleeps.append(seconds)
        clock[0] += seconds

    responses = iter(
        [
            _response(
                429,
                b"<error><message>Rate limit exceeded.</message></error>",
            ),
            _response(200, b"<items><item objectid='2'/></items>"),
            _response(200, b"<items><item objectid='1'/></items>"),
        ]
    )
    requested_users: list[str] = []

    get_user_collections._process_batch(
        connection,
        get_user_collections._load_collection_user_batch(connection, 100),
        sleep_fn=sleep_for,
        monotonic_fn=monotonic,
        request_fn=lambda username: (
            requested_users.append(username) or next(responses)
        ),
    )

    assert requested_users == ["alice", "bob", "alice"]
    assert sleeps == [30.0]
    connection.close()
