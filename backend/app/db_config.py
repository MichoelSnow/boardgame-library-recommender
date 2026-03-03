import os
from pathlib import Path
from typing import Any


def get_default_sqlite_path() -> str:
    return str(Path(__file__).parent.parent / "database" / "boardgames.db")


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    database_path = os.getenv("DATABASE_PATH", get_default_sqlite_path())
    if database_path.startswith("sqlite:///"):
        return database_path
    return f"sqlite:///{database_path}"


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
