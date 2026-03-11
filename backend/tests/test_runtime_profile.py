import pytest

from backend.app.runtime_profile import (
    RuntimeSettings,
    build_server_command,
    resolve_runtime_settings,
)


def test_resolve_runtime_settings_standard_defaults() -> None:
    settings = resolve_runtime_settings({})

    assert settings.runtime_profile == "standard"
    assert settings.app_server == "uvicorn"
    assert settings.gunicorn_workers == 1


def test_resolve_runtime_settings_convention_defaults() -> None:
    settings = resolve_runtime_settings({"RUNTIME_PROFILE": "convention"})

    assert settings.runtime_profile == "convention"
    assert settings.app_server == "gunicorn"
    assert settings.gunicorn_workers == 3


def test_resolve_runtime_settings_override_server_and_workers() -> None:
    settings = resolve_runtime_settings(
        {
            "RUNTIME_PROFILE": "rehearsal",
            "APP_SERVER": "uvicorn",
            "GUNICORN_WORKERS": "4",
        }
    )

    assert settings.runtime_profile == "rehearsal"
    assert settings.app_server == "uvicorn"
    assert settings.gunicorn_workers == 4


def test_resolve_runtime_settings_invalid_runtime_profile() -> None:
    with pytest.raises(RuntimeError, match="Invalid RUNTIME_PROFILE"):
        resolve_runtime_settings({"RUNTIME_PROFILE": "invalid"})


def test_resolve_runtime_settings_invalid_app_server() -> None:
    with pytest.raises(RuntimeError, match="Invalid APP_SERVER"):
        resolve_runtime_settings({"APP_SERVER": "invalid"})


def test_resolve_runtime_settings_invalid_workers() -> None:
    with pytest.raises(RuntimeError, match="GUNICORN_WORKERS must be >= 1"):
        resolve_runtime_settings({"GUNICORN_WORKERS": "0"})


def test_build_server_command_uvicorn() -> None:
    settings = RuntimeSettings(
        runtime_profile="standard", app_server="uvicorn", gunicorn_workers=1
    )
    assert build_server_command(settings) == [
        "uvicorn",
        "backend.app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8080",
    ]


def test_build_server_command_gunicorn() -> None:
    settings = RuntimeSettings(
        runtime_profile="convention", app_server="gunicorn", gunicorn_workers=2
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
