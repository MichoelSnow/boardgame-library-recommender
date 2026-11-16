"""Fetch selected BoardGameGeek user collections after ratings ingestion.

Collection exports are asynchronous on BoardGameGeek.  A request may return a
queued response before the collection XML is ready, so this stage keeps a
durable per-user queue in a separate DuckDB artifact and resumes completed and
pending work safely.
"""

from __future__ import annotations

import argparse
import heapq
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from time import monotonic, sleep, time

import duckdb
import requests
from bs4 import BeautifulSoup

try:
    from ..common.bgg_auth import build_bgg_auth_headers
    from ..common.ingest_utils import latest_file, utc_now_iso
    from ..common.logging_utils import configure_stage_logging
except ImportError:
    from data_pipeline.src.common.bgg_auth import build_bgg_auth_headers
    from data_pipeline.src.common.ingest_utils import latest_file, utc_now_iso
    from data_pipeline.src.common.logging_utils import configure_stage_logging

logger = logging.getLogger(__name__)

_build_bgg_auth_headers = build_bgg_auth_headers
_latest_file = latest_file
_utc_now_iso = utc_now_iso

COLLECTION_URL = "https://boardgamegeek.com/xmlapi2/collection"
REQUEST_TIMEOUT_SECONDS = 30
DEFAULT_BATCH_SIZE = 100
DEFAULT_COVERAGE_PERCENT = 90.0
MIN_REQUEST_INTERVAL_SECONDS = 6.0
INITIAL_PENDING_RETRY_SECONDS = 15.0
MAX_PENDING_RETRY_SECONDS = 300.0
MAX_TRANSIENT_ATTEMPTS = 8
TERMINAL_STATUSES = {"complete", "too_large", "invalid_user"}


@dataclass(frozen=True)
class CollectionResponse:
    kind: str
    message: str | None
    items: list[dict[str, object]]
    retry_after_seconds: float | None = None


def _validate_selection_options(
    *,
    coverage_percent: float | None,
    max_users: int | None,
    additional_users: int | None,
    batch_size: int,
) -> None:
    selection_values = [coverage_percent, max_users, additional_users]
    if sum(value is not None for value in selection_values) != 1:
        raise ValueError(
            "exactly one of coverage_percent, max_users, or additional_users is required"
        )
    if coverage_percent is not None and not 0 < coverage_percent <= 100:
        raise ValueError("coverage_percent must be greater than 0 and at most 100")
    if max_users is not None and max_users < 1:
        raise ValueError("max_users must be at least 1")
    if additional_users is not None and additional_users < 1:
        raise ValueError("additional_users must be at least 1")
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")


def _initialize_collection_store(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS collection_metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS collection_users (
            username TEXT PRIMARY KEY,
            rating_count BIGINT NOT NULL,
            selection_rank BIGINT NOT NULL,
            cumulative_rating_count BIGINT NOT NULL,
            total_rating_count BIGINT NOT NULL,
            coverage_percent DOUBLE NOT NULL,
            status TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_http_status INTEGER,
            last_message TEXT,
            last_error TEXT,
            next_attempt_at TEXT,
            completed_at TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_collection_items (
            username TEXT NOT NULL,
            game_id BIGINT NOT NULL,
            collection_id BIGINT,
            object_type TEXT,
            subtype TEXT,
            name TEXT,
            original_name TEXT,
            year_published INTEGER,
            own INTEGER,
            previously_owned INTEGER,
            for_trade INTEGER,
            want INTEGER,
            want_to_play INTEGER,
            want_to_buy INTEGER,
            wishlist INTEGER,
            wishlist_priority INTEGER,
            preordered INTEGER,
            last_modified TEXT,
            num_plays INTEGER,
            rating DOUBLE,
            comment TEXT,
            condition_text TEXT
        );
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_collection_items_user
            ON user_collection_items(username);
        CREATE INDEX IF NOT EXISTS idx_user_collection_items_game
            ON user_collection_items(game_id);
        """
    )


def _set_metadata(
    connection: duckdb.DuckDBPyConnection, values: dict[str, str]
) -> None:
    connection.executemany(
        "INSERT OR REPLACE INTO collection_metadata (key, value) VALUES (?, ?)",
        list(values.items()),
    )


def _get_metadata(connection: duckdb.DuckDBPyConnection) -> dict[str, str]:
    return {
        str(key): str(value)
        for key, value in connection.execute(
            "SELECT key, value FROM collection_metadata"
        ).fetchall()
    }


def _log_collection_progress(
    connection: duckdb.DuckDBPyConnection, message: str
) -> None:
    counts = {
        str(status): int(count)
        for status, count in connection.execute(
            """
            SELECT status, COUNT(*)
            FROM collection_users
            GROUP BY status
            """
        ).fetchall()
    }
    failed_count = counts.get("failed", 0) + counts.get("invalid_user", 0)
    total = sum(counts.values())
    logger.info(
        "%s: total=%d complete=%d too_large=%d failed=%d queued=%d pending=%d",
        message,
        total,
        counts.get("complete", 0),
        counts.get("too_large", 0),
        failed_count,
        counts.get("queued", 0),
        counts.get("pending", 0),
    )


def _populate_selected_users(
    connection: duckdb.DuckDBPyConnection,
    ratings_db_path: Path,
    *,
    coverage_percent: float | None,
    max_users: int | None,
    additional_users: int | None = None,
    existing_user_count: int = 0,
) -> int:
    """Populate selection and status rows without materializing users in Python."""
    ratings_db_literal = str(ratings_db_path).replace("'", "''")
    logger.info(
        "Building collection user queue from ratings DuckDB: %s", ratings_db_path
    )
    connection.execute(f"ATTACH '{ratings_db_literal}' AS ratings_source (READ_ONLY)")
    try:
        if max_users is not None:
            if existing_user_count:
                selection_filter = "selection_rank > ? AND selection_rank <= ?"
                selection_parameters: list[object] = [
                    existing_user_count,
                    max_users,
                ]
            else:
                selection_filter = "selection_rank <= ?"
                selection_parameters = [max_users]
        elif additional_users is not None:
            selection_filter = "selection_rank > ? AND selection_rank <= ?"
            selection_parameters = [
                existing_user_count,
                existing_user_count + additional_users,
            ]
        else:
            selection_filter = (
                "cumulative_rating_count - rating_count < total_rating_count * ? / 100"
            )
            selection_parameters = [coverage_percent]

        connection.execute(
            f"""
            INSERT INTO collection_users (
                username, rating_count, selection_rank, cumulative_rating_count,
                total_rating_count, coverage_percent, status, updated_at
            )
            WITH user_counts AS (
                SELECT
                    username,
                    COUNT(game_id) AS rating_count
                FROM ratings_source.main.boardgame_ratings
                WHERE username IS NOT NULL AND trim(username) <> ''
                GROUP BY username
            ), ranked_users AS (
                SELECT
                    username,
                    rating_count,
                    SUM(rating_count) OVER () AS total_rating_count,
                    SUM(rating_count) OVER (
                        ORDER BY rating_count DESC, username
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    ) AS cumulative_rating_count,
                    ROW_NUMBER() OVER (
                        ORDER BY rating_count DESC, username
                    ) AS selection_rank
                FROM user_counts
            )
            SELECT
                username,
                rating_count,
                selection_rank,
                cumulative_rating_count,
                total_rating_count,
                cumulative_rating_count * 100.0 / total_rating_count,
                'pending',
                ?
            FROM ranked_users
            WHERE {selection_filter}
            """,
            [_utc_now_iso(), *selection_parameters],
        )
    finally:
        connection.execute("DETACH ratings_source")

    selected_count, selected_ratings, total_ratings, achieved_coverage = (
        connection.execute(
            """
            SELECT
                COUNT(*),
                COALESCE(SUM(rating_count), 0),
                COALESCE(MAX(total_rating_count), 0),
                COALESCE(MAX(coverage_percent), 0)
            FROM collection_users
            """
        ).fetchone()
    )
    logger.info(
        "Selected %d users covering %d of %d rating rows (%.2f%%)",
        selected_count,
        selected_ratings,
        total_ratings,
        achieved_coverage,
    )
    return int(selected_count)


def _collection_user_counts(
    connection: duckdb.DuckDBPyConnection,
) -> tuple[int, int]:
    count, max_selection_rank = connection.execute(
        """
        SELECT COUNT(*), COALESCE(MAX(selection_rank), 0)
        FROM collection_users
        """
    ).fetchone()
    return int(count), int(max_selection_rank)


def _reset_failed_users(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        UPDATE collection_users
        SET status = 'pending', attempts = 0, last_error = NULL,
            next_attempt_at = NULL, updated_at = ?
        WHERE status = 'failed'
        """,
        [_utc_now_iso()],
    )


def _load_collection_user_batch(
    connection: duckdb.DuckDBPyConnection, batch_size: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT username, selection_rank, status, attempts
        FROM collection_users
        WHERE status IN ('pending', 'queued')
        ORDER BY selection_rank
        LIMIT ?
        """,
        [batch_size],
    ).fetchall()
    return [
        {
            "username": str(row[0]),
            "selection_rank": int(row[1]),
            "status": str(row[2]),
            "attempts": int(row[3]),
        }
        for row in rows
    ]


def _update_user(
    connection: duckdb.DuckDBPyConnection,
    username: str,
    *,
    status: str,
    attempts: int,
    http_status: int | None = None,
    message: str | None = None,
    error: str | None = None,
    next_attempt_at: str | None = None,
    completed_at: str | None = None,
) -> None:
    connection.execute(
        """
        UPDATE collection_users
        SET status = ?, attempts = ?, last_http_status = ?, last_message = ?,
            last_error = ?, next_attempt_at = ?, completed_at = ?, updated_at = ?
        WHERE username = ?
        """,
        [
            status,
            attempts,
            http_status,
            message,
            error,
            next_attempt_at,
            completed_at,
            _utc_now_iso(),
            username,
        ],
    )


def _parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_float(value: str | None) -> float | None:
    if value is None or value in {"", "N/A"}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _element_text(item: object, tag_name: str) -> str | None:
    element = item.find(tag_name)  # type: ignore[attr-defined]
    return element.get_text(strip=True) if element else None  # type: ignore[union-attr]


def _parse_collection_items(content: bytes, username: str) -> CollectionResponse:
    soup = BeautifulSoup(content, "xml")
    message_element = soup.find("message")
    message = message_element.get_text(" ", strip=True) if message_element else None
    normalized_message = (message or "").lower()

    if message and "exceeds maximum export size" in normalized_message:
        return CollectionResponse("too_large", message, [])

    if message and "invalid username specified" in normalized_message:
        return CollectionResponse("invalid_user", message, [])

    items = soup.find_all("item")
    if message and not items:
        pending_markers = ("accepted", "processed", "try again", "queued")
        if any(marker in normalized_message for marker in pending_markers):
            return CollectionResponse("pending", message, [])
        return CollectionResponse("failed", message, [])

    parsed_items: list[dict[str, object]] = []
    for item in items:
        game_id = _parse_int(item.get("objectid"))
        if game_id is None:
            continue
        status = item.find("status")
        rating_element = item.find("rating")
        numplays_element = item.find("numplays")
        parsed_items.append(
            {
                "username": username,
                "game_id": game_id,
                "collection_id": _parse_int(item.get("collid")),
                "object_type": item.get("objecttype"),
                "subtype": item.get("subtype"),
                "name": _element_text(item, "name"),
                "original_name": _element_text(item, "originalname"),
                "year_published": _parse_int(_element_text(item, "yearpublished")),
                "own": _parse_int(status.get("own") if status else None),
                "previously_owned": _parse_int(
                    status.get("prevowned") if status else None
                ),
                "for_trade": _parse_int(status.get("fortrade") if status else None),
                "want": _parse_int(status.get("want") if status else None),
                "want_to_play": _parse_int(
                    status.get("wanttoplay") if status else None
                ),
                "want_to_buy": _parse_int(status.get("wanttobuy") if status else None),
                "wishlist": _parse_int(status.get("wishlist") if status else None),
                "wishlist_priority": _parse_int(
                    status.get("wishlistpriority") if status else None
                ),
                "preordered": _parse_int(status.get("preordered") if status else None),
                "last_modified": status.get("lastmodified") if status else None,
                "num_plays": _parse_int(
                    numplays_element.get_text(strip=True) if numplays_element else None
                ),
                "rating": _parse_float(
                    rating_element.get("value") if rating_element else None
                ),
                "comment": _element_text(item, "comment"),
                "condition_text": _element_text(item, "conditiontext"),
            }
        )
    return CollectionResponse("ready", message, parsed_items)


def _request_collection(username: str) -> requests.Response:
    return requests.get(
        COLLECTION_URL,
        params={"username": username, "stats": 1, "numplays": 1},
        headers=_build_bgg_auth_headers(),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )


def _retry_after_seconds(response: requests.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        return max(0.0, (retry_at - datetime.now(UTC)).total_seconds())


def _classify_response(
    response: requests.Response, username: str
) -> CollectionResponse:
    if response.status_code in {401, 403}:
        raise RuntimeError(
            f"BGG authorization failed while fetching {username} "
            f"(HTTP {response.status_code})"
        )
    if response.status_code in {429, 500, 502, 503, 504}:
        return CollectionResponse(
            "transient",
            response.text,
            [],
            retry_after_seconds=_retry_after_seconds(response),
        )

    parsed = _parse_collection_items(response.content, username)
    if parsed.kind == "failed" and response.status_code == 202:
        return CollectionResponse("pending", parsed.message, [])
    if response.status_code >= 400:
        return CollectionResponse("failed", parsed.message or response.text, [])
    return parsed


def _save_collection_items(
    connection: duckdb.DuckDBPyConnection,
    username: str,
    items: list[dict[str, object]],
) -> None:
    connection.execute(
        "DELETE FROM user_collection_items WHERE username = ?", [username]
    )
    if not items:
        return
    columns = [
        "username",
        "game_id",
        "collection_id",
        "object_type",
        "subtype",
        "name",
        "original_name",
        "year_published",
        "own",
        "previously_owned",
        "for_trade",
        "want",
        "want_to_play",
        "want_to_buy",
        "wishlist",
        "wishlist_priority",
        "preordered",
        "last_modified",
        "num_plays",
        "rating",
        "comment",
        "condition_text",
    ]
    values = [tuple(item.get(column) for column in columns) for item in items]
    placeholders = ", ".join("?" for _ in columns)
    connection.executemany(
        f"INSERT INTO user_collection_items ({', '.join(columns)}) VALUES ({placeholders})",
        values,
    )


def _find_or_create_store(
    collections_dir: Path,
    ratings_db_path: Path,
    *,
    continue_from_last: bool,
    coverage_percent: float | None,
    max_users: int | None,
    additional_users: int | None,
    selection_mode: str,
    selection_value: float | int,
) -> tuple[Path, duckdb.DuckDBPyConnection]:
    collections_dir.mkdir(parents=True, exist_ok=True)
    existing_files = list(collections_dir.glob("user_collections_*.duckdb"))
    existing_store = (
        _latest_file(collections_dir, "user_collections_*.duckdb")
        if continue_from_last and existing_files
        else None
    )
    if existing_store is not None:
        connection = duckdb.connect(str(existing_store))
        _initialize_collection_store(connection)
        metadata = _get_metadata(connection)
        if metadata.get("source_ratings_db") == str(ratings_db_path):
            _reset_failed_users(connection)
            existing_user_count, existing_selection_rank = _collection_user_counts(
                connection
            )
            if max_users is not None:
                selected_user_count = existing_user_count
                if existing_selection_rank < max_users:
                    selected_user_count = _populate_selected_users(
                        connection,
                        ratings_db_path,
                        coverage_percent=None,
                        max_users=max_users,
                        additional_users=None,
                        existing_user_count=existing_selection_rank,
                    )
                _set_metadata(
                    connection,
                    {
                        "selection_mode": selection_mode,
                        "selection_value": str(selection_value),
                        "selected_user_count": str(selected_user_count),
                        "updated_at_utc": _utc_now_iso(),
                    },
                )
                metadata.update(
                    {
                        "selection_mode": selection_mode,
                        "selection_value": str(selection_value),
                    }
                )
                added_count = selected_user_count - existing_user_count
                if added_count:
                    logger.info(
                        "Added %d users to existing collection queue "
                        "(%d total; target=%d)",
                        added_count,
                        selected_user_count,
                        max_users,
                    )
                else:
                    logger.info(
                        "Existing collection queue already has %d users; "
                        "max-users target is %d",
                        existing_user_count,
                        max_users,
                    )
            elif additional_users is not None:
                selected_user_count = _populate_selected_users(
                    connection,
                    ratings_db_path,
                    coverage_percent=None,
                    max_users=None,
                    additional_users=additional_users,
                    existing_user_count=existing_selection_rank,
                )
                _set_metadata(
                    connection,
                    {
                        "selection_mode": selection_mode,
                        "selection_value": str(selection_value),
                        "selected_user_count": str(selected_user_count),
                        "updated_at_utc": _utc_now_iso(),
                    },
                )
                metadata.update(
                    {
                        "selection_mode": selection_mode,
                        "selection_value": str(selection_value),
                    }
                )
                logger.info(
                    "Added %d users to existing collection queue (%d total)",
                    selected_user_count - existing_user_count,
                    selected_user_count,
                )
            connection.commit()
            logger.info(
                "Continuing from user collections DuckDB: %s (selection=%s %s)",
                existing_store,
                metadata.get("selection_mode", "unknown"),
                metadata.get("selection_value", "unknown"),
            )
            return existing_store, connection
        logger.info(
            "Latest user collections artifact belongs to a different ratings file; "
            "starting a new collection artifact."
        )
        connection.close()

    store_timestamp = int(time() * 1000)
    store_path = collections_dir / f"user_collections_{store_timestamp}.duckdb"
    while store_path.exists():
        store_timestamp += 1
        store_path = collections_dir / f"user_collections_{store_timestamp}.duckdb"
    connection = duckdb.connect(str(store_path))
    _initialize_collection_store(connection)
    selected_user_count = _populate_selected_users(
        connection,
        ratings_db_path,
        coverage_percent=coverage_percent,
        max_users=max_users,
        additional_users=additional_users,
    )
    _set_metadata(
        connection,
        {
            "source_ratings_db": str(ratings_db_path),
            "selection_mode": selection_mode,
            "selection_value": str(selection_value),
            "selected_user_count": str(selected_user_count),
            "created_at_utc": _utc_now_iso(),
        },
    )
    connection.commit()
    logger.info(
        "Created user collections DuckDB: %s (selection=%s %s, users=%d)",
        store_path,
        selection_mode,
        selection_value,
        selected_user_count,
    )
    return store_path, connection


def _process_batch(
    connection: duckdb.DuckDBPyConnection,
    users: list[dict[str, object]],
    *,
    sleep_fn: Callable[[float], None] = sleep,
    monotonic_fn: Callable[[], float] = monotonic,
    request_fn: Callable[[str], requests.Response] = _request_collection,
    global_cooldown_until: list[float] | None = None,
) -> int:
    queue: list[tuple[float, int, str, int]] = []
    sequence = 0
    skipped_terminal = 0
    batch_states: dict[str, str] = {}
    complete_count = 0
    failed_count = 0
    retry_queued_count = 0
    for user in users:
        username = str(user["username"])
        status = str(user["status"])
        if status == "complete":
            batch_states[username] = "complete"
            complete_count += 1
        elif status in {"too_large", "failed", "invalid_user"}:
            batch_states[username] = "failed"
            failed_count += 1
        elif status == "queued":
            batch_states[username] = "retry_queued"
            retry_queued_count += 1
        else:
            batch_states[username] = "not_requested"

        if status in TERMINAL_STATUSES:
            skipped_terminal += 1
            continue
        heapq.heappush(
            queue,
            (0.0, sequence, username, int(user["attempts"])),
        )
        sequence += 1

    logger.info(
        "Starting collection batch with %d users (%d queued, %d already terminal)",
        len(users),
        len(queue),
        skipped_terminal,
    )
    last_request_at: float | None = None
    cooldown_state = (
        global_cooldown_until if global_cooldown_until is not None else [0.0]
    )
    failed_users: set[str] = set()
    while queue:
        due_at, _, username, attempts = heapq.heappop(queue)
        now = monotonic_fn()
        if due_at > now:
            sleep_fn(due_at - now)

        now = monotonic_fn()
        if cooldown_state[0] > now:
            cooldown_seconds = cooldown_state[0] - now
            logger.info(
                "Global request cooldown active; waiting %.1f seconds before "
                "requesting %s",
                cooldown_seconds,
                username,
            )
            sleep_fn(cooldown_seconds)

        if last_request_at is not None:
            elapsed = monotonic_fn() - last_request_at
            if elapsed < MIN_REQUEST_INTERVAL_SECONDS:
                sleep_fn(MIN_REQUEST_INTERVAL_SECONDS - elapsed)

        response: requests.Response | None = None
        logger.info("Requesting collection for %s (attempt %d)", username, attempts + 1)
        if batch_states[username] == "retry_queued":
            retry_queued_count -= 1
        batch_states[username] = "in_progress"
        try:
            response = request_fn(username)
            last_request_at = monotonic_fn()
            result = _classify_response(response, username)
        except requests.RequestException as exc:
            last_request_at = monotonic_fn()
            result = CollectionResponse("transient", str(exc), [])
            logger.warning(
                "Collection request for %s raised %s; treating it as transient",
                username,
                exc,
            )

        next_attempts = attempts + 1
        rate_limit_delay: float | None = None
        if response is not None and response.status_code == 429:
            rate_limit_delay = min(
                result.retry_after_seconds
                if result.retry_after_seconds is not None
                else 30.0 * (2 ** max(attempts - 1, 0)),
                MAX_PENDING_RETRY_SECONDS,
            )
            cooldown_state[0] = max(
                cooldown_state[0],
                monotonic_fn() + rate_limit_delay,
            )
            logger.warning(
                "Global request cooldown after HTTP 429: pausing all requests "
                "for %.1f seconds",
                rate_limit_delay,
            )
        if result.kind == "ready":
            _save_collection_items(connection, username, result.items)
            _update_user(
                connection,
                username,
                status="complete",
                attempts=next_attempts,
                http_status=response.status_code if response is not None else None,
                message=result.message,
                completed_at=_utc_now_iso(),
            )
            connection.commit()
            logger.info(
                "Completed collection for %s (attempt %d, HTTP %s, %d items)",
                username,
                next_attempts,
                response.status_code if response is not None else "n/a",
                len(result.items),
            )
            batch_states[username] = "complete"
            complete_count += 1
        elif result.kind == "invalid_user":
            _update_user(
                connection,
                username,
                status="invalid_user",
                attempts=next_attempts,
                http_status=response.status_code if response is not None else None,
                message=result.message,
                error=result.message or "invalid username",
            )
            connection.commit()
            logger.error(
                "Failed collection for %s (attempt %d, HTTP %s): %s",
                username,
                next_attempts,
                response.status_code if response is not None else "n/a",
                result.message,
            )
            batch_states[username] = "failed"
            failed_count += 1
        elif result.kind == "too_large":
            _update_user(
                connection,
                username,
                status="too_large",
                attempts=next_attempts,
                http_status=response.status_code if response is not None else None,
                message=result.message,
            )
            connection.commit()
            logger.warning(
                "Skipping oversized collection for %s (attempt %d, HTTP %s): %s",
                username,
                next_attempts,
                response.status_code if response is not None else "n/a",
                result.message,
            )
            batch_states[username] = "failed"
            failed_count += 1
        elif result.kind == "pending":
            delay = min(
                result.retry_after_seconds
                or INITIAL_PENDING_RETRY_SECONDS * (2 ** max(attempts - 1, 0)),
                MAX_PENDING_RETRY_SECONDS,
            )
            next_at = time() + delay
            _update_user(
                connection,
                username,
                status="queued",
                attempts=next_attempts,
                http_status=response.status_code if response is not None else None,
                message=result.message,
                next_attempt_at=datetime.fromtimestamp(next_at, UTC).isoformat(),
            )
            connection.commit()
            logger.info(
                "Collection for %s is pending (attempt %d, HTTP %s); "
                "retrying in %.1f seconds: %s",
                username,
                next_attempts,
                response.status_code if response is not None else "n/a",
                delay,
                result.message,
            )
            batch_states[username] = "retry_queued"
            retry_queued_count += 1
            heapq.heappush(
                queue, (monotonic_fn() + delay, sequence, username, next_attempts)
            )
            sequence += 1
        elif result.kind == "transient" and next_attempts < MAX_TRANSIENT_ATTEMPTS:
            delay = (
                rate_limit_delay
                if rate_limit_delay is not None
                else min(
                    result.retry_after_seconds
                    if result.retry_after_seconds is not None
                    else 30.0 * (2 ** max(attempts - 1, 0)),
                    MAX_PENDING_RETRY_SECONDS,
                )
            )
            _update_user(
                connection,
                username,
                status="queued",
                attempts=next_attempts,
                http_status=response.status_code if response is not None else None,
                message=result.message,
                next_attempt_at=datetime.fromtimestamp(time() + delay, UTC).isoformat(),
            )
            connection.commit()
            logger.warning(
                "Transient collection response for %s (attempt %d, HTTP %s); "
                "retrying in %.1f seconds: %s",
                username,
                next_attempts,
                response.status_code if response is not None else "n/a",
                delay,
                result.message,
            )
            batch_states[username] = "retry_queued"
            retry_queued_count += 1
            heapq.heappush(
                queue, (monotonic_fn() + delay, sequence, username, next_attempts)
            )
            sequence += 1
        else:
            failed_users.add(username)
            _update_user(
                connection,
                username,
                status="failed",
                attempts=next_attempts,
                http_status=response.status_code if response is not None else None,
                message=result.message,
                error=result.message or "collection request failed",
            )
            connection.commit()
            logger.error(
                "Failed collection for %s (attempt %d, HTTP %s): %s",
                username,
                next_attempts,
                response.status_code if response is not None else "n/a",
                result.message,
            )
            batch_states[username] = "failed"
            failed_count += 1

        logger.info(
            "total=%d complete=%d failed=%d retry_queued=%d",
            len(users),
            complete_count,
            failed_count,
            retry_queued_count,
        )

    return len(failed_users)


def ingest_user_collections(
    *,
    ratings_db_path: Path,
    collections_dir: Path,
    continue_from_last: bool = False,
    batch_size: int = DEFAULT_BATCH_SIZE,
    coverage_percent: float | None = DEFAULT_COVERAGE_PERCENT,
    max_users: int | None = None,
    additional_users: int | None = None,
) -> Path:
    """Ingest selected users' complete collections into a DuckDB artifact."""
    logger.info(
        "Starting user collection ingestion (ratings_db=%s, collections_dir=%s, "
        "continue_from_last=%s, batch_size=%d, coverage_percent=%s, max_users=%s, "
        "additional_users=%s, "
        "request_interval=%.1fs)",
        ratings_db_path,
        collections_dir,
        continue_from_last,
        batch_size,
        coverage_percent,
        max_users,
        additional_users,
        MIN_REQUEST_INTERVAL_SECONDS,
    )
    _validate_selection_options(
        coverage_percent=coverage_percent,
        max_users=max_users,
        additional_users=additional_users,
        batch_size=batch_size,
    )
    ratings_db_path = ratings_db_path.resolve()
    if max_users is not None:
        selection_mode = "max_users"
        selection_value: float | int = max_users
    elif additional_users is not None:
        selection_mode = "additional_users"
        selection_value = additional_users
    else:
        selection_mode = "coverage_percent"
        selection_value = float(coverage_percent)
    _, connection = _find_or_create_store(
        collections_dir,
        ratings_db_path,
        continue_from_last=continue_from_last,
        coverage_percent=coverage_percent,
        max_users=max_users,
        additional_users=additional_users,
        selection_mode=selection_mode,
        selection_value=selection_value,
    )

    failed_count = 0
    global_cooldown_until = [0.0]
    try:
        _log_collection_progress(connection, "Collection queue before processing")
        batch_number = 0
        while True:
            batch = _load_collection_user_batch(connection, batch_size)
            if not batch:
                break
            batch_number += 1
            logger.info(
                "Processing collection batch %d (%d users)",
                batch_number,
                len(batch),
            )
            failed_in_batch = _process_batch(
                connection,
                batch,
                global_cooldown_until=global_cooldown_until,
            )
            failed_count += failed_in_batch
            _log_collection_progress(
                connection,
                f"Collection progress after batch {batch_number} "
                f"(batch failures={failed_in_batch})",
            )
    finally:
        connection.close()

    logger.info("User collection ingestion finished; failed users=%d", failed_count)
    if failed_count:
        raise RuntimeError(f"{failed_count} user collection requests failed")
    return _latest_file(collections_dir, "user_collections_*.duckdb")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch selected BGG user collections after ratings ingestion."
    )
    parser.add_argument("--continue-from-last", action="store_true")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--coverage-percent",
        type=float,
        default=DEFAULT_COVERAGE_PERCENT,
        help="Rating-row coverage target (default: 90).",
    )
    selection.add_argument(
        "--max-users",
        type=int,
        help="Stop after selecting this many users instead of using coverage.",
    )
    selection.add_argument(
        "--additional-users",
        type=int,
        help="Add this many users after the users already selected in the collection DuckDB.",
    )
    parser.add_argument("--ratings-db", type=Path)
    parser.add_argument("--collections-dir", type=Path)
    return parser.parse_args()


def main() -> int:
    configure_stage_logging(logger, "get_user_collections.log")
    args = parse_args()
    project_root = Path(__file__).resolve().parents[3]
    ratings_dir = project_root / "data" / "ingest" / "ratings"
    collections_dir = (
        args.collections_dir or project_root / "data" / "ingest" / "collections"
    )
    ratings_db = args.ratings_db or _latest_file(
        ratings_dir, "boardgame_ratings_*.duckdb"
    )
    ingest_user_collections(
        ratings_db_path=ratings_db,
        collections_dir=collections_dir,
        continue_from_last=args.continue_from_last,
        batch_size=args.batch_size,
        coverage_percent=(
            None
            if args.max_users is not None or args.additional_users is not None
            else args.coverage_percent
        ),
        max_users=args.max_users,
        additional_users=args.additional_users,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
