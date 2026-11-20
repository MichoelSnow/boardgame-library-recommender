import pytest

from backend.app.db_keepalive import (
    resolve_keepalive_interval_seconds,
    should_enable_db_keepalive,
)


def test_should_enable_db_keepalive_for_postgres_by_default():
    assert should_enable_db_keepalive(
        "postgresql+psycopg2://u:p@localhost/db", {}
    ) is True


def test_should_enable_db_keepalive_respects_explicit_disable():
    assert should_enable_db_keepalive(
        "postgresql+psycopg2://u:p@localhost/db",
        {"DB_KEEPALIVE_ENABLED": "false"},
    ) is False


def test_resolve_keepalive_interval_rejects_invalid_values():
    with pytest.raises(RuntimeError, match="positive integer"):
        resolve_keepalive_interval_seconds({"DB_KEEPALIVE_INTERVAL_SECONDS": "abc"})

    with pytest.raises(RuntimeError, match=">= 5 seconds"):
        resolve_keepalive_interval_seconds({"DB_KEEPALIVE_INTERVAL_SECONDS": "2"})
