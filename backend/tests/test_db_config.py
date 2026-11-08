import pytest

from backend.app import db_config


def test_get_database_url_prefers_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_BACKEND", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/library")

    result = db_config.get_database_url()

    assert result == "postgresql+psycopg2://user:pass@localhost:5432/library"


def test_get_database_url_requires_database_url_in_production(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_BACKEND", raising=False)
    monkeypatch.setenv("NODE_ENV", "production")

    with pytest.raises(RuntimeError, match="DATABASE_URL must be set"):
        db_config.get_database_url()


def test_get_database_url_does_not_use_backend_switch_in_production(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_BACKEND", "postgres")
    monkeypatch.setenv("NODE_ENV", "production")

    with pytest.raises(RuntimeError, match="Refusing to use DATABASE_BACKEND"):
        db_config.get_database_url()


def test_get_database_url_builds_local_postgres_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_BACKEND", "postgres")
    monkeypatch.setenv("POSTGRES_USER", "postgres")
    monkeypatch.setenv("POSTGRES_PASSWORD_LOCAL", "p@ss:word")
    monkeypatch.setenv("POSTGRES_HOST_LOCAL", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_PORT_LOCAL", "5432")
    monkeypatch.setenv("POSTGRES_DB", "boardgame_recommender")

    result = db_config.get_database_url()

    assert (
        result
        == "postgresql+psycopg2://postgres:p%40ss%3Aword@127.0.0.1:5432/boardgame_recommender"
    )


def test_get_database_url_rejects_unknown_backend(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_BACKEND", "mysql")

    with pytest.raises(RuntimeError, match="DATABASE_BACKEND must be either"):
        db_config.get_database_url()


def test_get_database_url_requires_explicit_nonproduction_configuration(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_BACKEND", raising=False)
    monkeypatch.setenv("NODE_ENV", "development")

    with pytest.raises(RuntimeError, match="Database backend is not configured"):
        db_config.get_database_url()


def test_get_engine_kwargs_uses_postgres_pooling_defaults():
    result = db_config.get_engine_kwargs(
        "postgresql+psycopg2://user:pass@localhost:5432/library"
    )

    assert "connect_args" not in result
    assert result["pool_pre_ping"] is True
