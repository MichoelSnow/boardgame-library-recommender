import argparse
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8080

VALID_RUNTIME_PROFILES = {"standard", "convention", "rehearsal"}
VALID_APP_SERVERS = {"uvicorn", "gunicorn"}


@dataclass(frozen=True)
class RuntimeSettings:
    runtime_profile: str
    app_server: str
    gunicorn_workers: int
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT


def _parse_positive_int(value: str, name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a positive integer, got '{value}'.") from exc
    if parsed < 1:
        raise RuntimeError(f"{name} must be >= 1, got '{value}'.")
    return parsed


def resolve_runtime_settings(env: dict[str, str] | None = None) -> RuntimeSettings:
    environment = env or os.environ

    runtime_profile = environment.get("RUNTIME_PROFILE", "standard").strip().lower()
    if runtime_profile not in VALID_RUNTIME_PROFILES:
        raise RuntimeError(
            f"Invalid RUNTIME_PROFILE '{runtime_profile}'. "
            f"Valid values: {sorted(VALID_RUNTIME_PROFILES)}."
        )

    app_server = environment.get("APP_SERVER", "").strip().lower()
    if not app_server:
        app_server = "uvicorn" if runtime_profile == "standard" else "gunicorn"
    if app_server not in VALID_APP_SERVERS:
        raise RuntimeError(
            f"Invalid APP_SERVER '{app_server}'. "
            f"Valid values: {sorted(VALID_APP_SERVERS)}."
        )

    default_workers = "3" if runtime_profile in {"convention", "rehearsal"} else "1"
    gunicorn_workers = _parse_positive_int(
        environment.get("GUNICORN_WORKERS", default_workers).strip(),
        "GUNICORN_WORKERS",
    )

    return RuntimeSettings(
        runtime_profile=runtime_profile,
        app_server=app_server,
        gunicorn_workers=gunicorn_workers,
    )


def build_server_command(settings: RuntimeSettings) -> list[str]:
    if settings.app_server == "uvicorn":
        return [
            "uvicorn",
            "backend.app.main:app",
            "--host",
            settings.host,
            "--port",
            str(settings.port),
        ]

    return [
        "gunicorn",
        "-k",
        "uvicorn.workers.UvicornWorker",
        "-w",
        str(settings.gunicorn_workers),
        "-b",
        f"{settings.host}:{settings.port}",
        "backend.app.main:app",
    ]


def serve() -> None:
    settings = resolve_runtime_settings()
    command = build_server_command(settings)
    logger.info(
        "Starting app with runtime profile '%s' using server '%s'%s",
        settings.runtime_profile,
        settings.app_server,
        f" (workers={settings.gunicorn_workers})" if settings.app_server == "gunicorn" else "",
    )
    os.execvp(command[0], command)


def main() -> int:
    parser = argparse.ArgumentParser(description="Runtime profile bootstrap for app server startup.")
    parser.add_argument("--serve", action="store_true", help="Execute the resolved server command.")
    args = parser.parse_args()

    if args.serve:
        serve()
        return 0

    settings = resolve_runtime_settings()
    command = build_server_command(settings)
    print(" ".join(command))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
