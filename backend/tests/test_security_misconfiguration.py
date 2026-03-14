import pytest

from backend.app import main


def test_get_cors_origins_rejects_wildcard_in_production(monkeypatch):
    monkeypatch.setenv("NODE_ENV", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")
    with pytest.raises(RuntimeError, match="Invalid production CORS configuration"):
        main.get_cors_origins()


def test_get_cors_origins_accepts_explicit_origins_in_production(monkeypatch):
    monkeypatch.setenv("NODE_ENV", "production")
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        "https://prod.example.com,https://dev.example.com",
    )
    origins = main.get_cors_origins()
    assert origins == [
        "https://prod.example.com",
        "https://dev.example.com",
    ]
