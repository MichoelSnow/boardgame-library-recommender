import pytest

from backend.app import db_config


def test_get_database_url_prefers_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/library")
    monkeypatch.setenv("DATABASE_PATH", "/tmp/ignored.db")

    result = db_config.get_database_url()

    assert result == "postgresql://user:pass@localhost:5432/library"


def test_get_database_url_falls_back_to_database_path(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("NODE_ENV", "development")
    monkeypatch.setenv("DATABASE_PATH", "/tmp/boardgames.db")

    result = db_config.get_database_url()

    assert result == "sqlite:////tmp/boardgames.db"


def test_get_database_url_preserves_sqlite_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("NODE_ENV", "development")
    monkeypatch.setenv("DATABASE_PATH", "sqlite:////tmp/boardgames.db")

    result = db_config.get_database_url()

    assert result == "sqlite:////tmp/boardgames.db"


def test_get_database_url_requires_database_url_in_production(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("NODE_ENV", "production")
    monkeypatch.setenv("DATABASE_PATH", "/tmp/boardgames.db")

    with pytest.raises(RuntimeError, match="DATABASE_URL must be set"):
        db_config.get_database_url()


def test_get_engine_kwargs_sets_sqlite_connect_args():
    result = db_config.get_engine_kwargs("sqlite:////tmp/boardgames.db")

    assert result["connect_args"] == {
        "check_same_thread": False,
        "timeout": 30.0,
    }
    assert result["pool_pre_ping"] is True


def test_get_engine_kwargs_omits_sqlite_connect_args_for_postgres():
    result = db_config.get_engine_kwargs(
        "postgresql://user:pass@localhost:5432/library"
    )

    assert "connect_args" not in result
    assert result["pool_pre_ping"] is True
