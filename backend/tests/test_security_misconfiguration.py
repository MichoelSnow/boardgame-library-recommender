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

    assert main.get_cors_origins() == [
        "https://prod.example.com",
        "https://dev.example.com",
    ]


def test_validate_startup_config_rejects_invalid_rate_limit_value(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_AUTH_PER_MIN", "abc")

    with pytest.raises(
        RuntimeError, match="RATE_LIMIT_AUTH_PER_MIN must be an integer"
    ):
        main.validate_startup_config()


def test_validate_startup_config_rejects_invalid_boolean_value(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "maybe")

    with pytest.raises(
        RuntimeError, match="RATE_LIMIT_ENABLED must be a boolean-like value"
    ):
        main.validate_startup_config()


def test_validate_startup_config_requires_guest_flag_in_convention_mode(monkeypatch):
    monkeypatch.setenv("CONVENTION_MODE", "true")
    monkeypatch.delenv("CONVENTION_GUEST_ENABLED", raising=False)

    with pytest.raises(
        RuntimeError,
        match="CONVENTION_GUEST_ENABLED must be explicitly set",
    ):
        main.validate_startup_config()
