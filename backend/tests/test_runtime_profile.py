import pytest

from backend.app.runtime_profile import (
    RuntimeSettings,
    build_server_command,
    resolve_runtime_settings,
)


def test_resolve_runtime_settings_standard_defaults():
    settings = resolve_runtime_settings({})

    assert settings.runtime_profile == "standard"
    assert settings.app_server == "uvicorn"
    assert settings.gunicorn_workers == 1


def test_resolve_runtime_settings_convention_defaults():
    settings = resolve_runtime_settings({"RUNTIME_PROFILE": "convention"})

    assert settings.runtime_profile == "convention"
    assert settings.app_server == "gunicorn"
    assert settings.gunicorn_workers == 3


def test_resolve_runtime_settings_rejects_invalid_profile():
    with pytest.raises(RuntimeError, match="Invalid RUNTIME_PROFILE"):
        resolve_runtime_settings({"RUNTIME_PROFILE": "invalid"})


def test_resolve_runtime_settings_rejects_invalid_worker_count():
    with pytest.raises(RuntimeError, match="GUNICORN_WORKERS must be >= 1"):
        resolve_runtime_settings({"GUNICORN_WORKERS": "0"})


def test_build_server_command_uses_configured_gunicorn_workers():
    settings = RuntimeSettings(
        runtime_profile="convention",
        app_server="gunicorn",
        gunicorn_workers=2,
    )

    assert build_server_command(settings) == [
        "gunicorn",
        "-k",
        "uvicorn.workers.UvicornWorker",
        "-w",
        "2",
        "-b",
        "0.0.0.0:8080",
        "backend.app.main:app",
    ]
