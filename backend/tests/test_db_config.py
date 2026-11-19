import pytest

from backend.app import db_config


def test_production_requires_explicit_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_BACKEND", raising=False)
    monkeypatch.setenv("NODE_ENV", "production")

    with pytest.raises(RuntimeError, match="DATABASE_URL must be set"):
        db_config.get_database_url()


def test_local_postgres_url_escapes_password(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_BACKEND", "postgres")
    monkeypatch.setenv("POSTGRES_USER", "postgres")
    monkeypatch.setenv("POSTGRES_PASSWORD_LOCAL", "p@ss:word")
    monkeypatch.setenv("POSTGRES_HOST_LOCAL", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_PORT_LOCAL", "5432")
    monkeypatch.setenv("POSTGRES_DB", "boardgame_recommender")

    assert db_config.get_database_url() == (
        "postgresql+psycopg2://postgres:p%40ss%3Aword@127.0.0.1:5432/boardgame_recommender"
    )
