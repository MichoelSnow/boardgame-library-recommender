import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy.engine import URL


REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env", override=False)


POSTGRES_LOCAL_VARIABLES = (
    "POSTGRES_USER",
    "POSTGRES_PASSWORD_LOCAL",
    "POSTGRES_HOST_LOCAL",
    "POSTGRES_PORT_LOCAL",
    "POSTGRES_DB",
)


def is_production_environment() -> bool:
    return os.getenv("NODE_ENV", "").strip().lower() == "production"


def get_default_sqlite_path() -> str:
    return str(Path(__file__).parent.parent / "database" / "boardgames.db")


def _get_sqlite_url() -> str:
    database_path = os.getenv("DATABASE_PATH", get_default_sqlite_path())
    if database_path.startswith("sqlite:///"):
        return database_path
    return f"sqlite:///{database_path}"


def _get_local_postgres_url() -> str:
    missing = [name for name in POSTGRES_LOCAL_VARIABLES if not os.getenv(name)]
    if missing:
        missing_names = ", ".join(missing)
        raise RuntimeError(
            "DATABASE_BACKEND=postgres requires these environment variables: "
            f"{missing_names}"
        )

    try:
        port = int(os.environ["POSTGRES_PORT_LOCAL"])
    except ValueError as exc:
        raise RuntimeError("POSTGRES_PORT_LOCAL must be an integer") from exc

    return URL.create(
        "postgresql+psycopg2",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD_LOCAL"],
        host=os.environ["POSTGRES_HOST_LOCAL"],
        port=port,
        database=os.environ["POSTGRES_DB"],
    ).render_as_string(hide_password=False)


def _normalize_postgres_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg2://", 1)
    return database_url


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")

    if is_production_environment():
        if not database_url:
            raise RuntimeError(
                "DATABASE_URL must be set when NODE_ENV=production. "
                "Refusing to use DATABASE_BACKEND for production."
            )
        return _normalize_postgres_url(database_url)

    if database_url:
        return _normalize_postgres_url(database_url)

    backend = os.getenv("DATABASE_BACKEND", "").strip().lower()

    if backend == "postgres":
        return _get_local_postgres_url()

    if backend == "sqlite":
        return _get_sqlite_url()

    if backend:
        raise RuntimeError(
            "DATABASE_BACKEND must be either 'postgres' or 'sqlite'; "
            f"received {backend!r}"
        )

    # DATABASE_URL remains the explicit deployment configuration for Fly and
    # for callers that provide a complete SQLAlchemy URL directly.
    raise RuntimeError(
        "Database backend is not configured. Set DATABASE_BACKEND to "
        "'postgres' or 'sqlite', or provide DATABASE_URL."
    )


def get_engine_kwargs(database_url: str) -> dict[str, Any]:
    engine_kwargs: dict[str, Any] = {
        "pool_size": 5,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "pool_pre_ping": True,
        "echo": False,
    }

    if database_url.startswith("sqlite:///"):
        engine_kwargs["connect_args"] = {
            "check_same_thread": False,
            "timeout": 30.0,
        }

    return engine_kwargs
