import asyncio
import logging
import os
from collections.abc import Callable
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

DEFAULT_KEEPALIVE_INTERVAL_SECONDS = 60


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def should_enable_db_keepalive(database_url: str, env: dict[str, str] | None = None) -> bool:
    environment = env or os.environ
    if not database_url.startswith("postgresql://"):
        return False
    return _is_truthy(environment.get("DB_KEEPALIVE_ENABLED", "true"))


def resolve_keepalive_interval_seconds(env: dict[str, str] | None = None) -> int:
    environment = env or os.environ
    raw_value = (environment.get("DB_KEEPALIVE_INTERVAL_SECONDS") or "").strip()
    if not raw_value:
        return DEFAULT_KEEPALIVE_INTERVAL_SECONDS
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(
            "DB_KEEPALIVE_INTERVAL_SECONDS must be a positive integer."
        ) from exc
    if value < 5:
        raise RuntimeError(
            "DB_KEEPALIVE_INTERVAL_SECONDS must be >= 5 seconds to avoid excessive polling."
        )
    return value


def ping_database(engine: Engine) -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


async def run_db_keepalive_loop(
    *,
    engine: Engine,
    interval_seconds: int,
    stop_event: asyncio.Event,
    ping_fn: Callable[[Engine], None] = ping_database,
) -> None:
    while not stop_event.is_set():
        try:
            ping_fn(engine)
            logger.info("DB keepalive ping succeeded.")
        except Exception as exc:  # pragma: no cover - safety net logging
            logger.warning("DB keepalive ping failed: %s", exc)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue


async def stop_keepalive_task(
    task: Optional[asyncio.Task],
    stop_event: Optional[asyncio.Event],
) -> None:
    if stop_event is not None:
        stop_event.set()
    if task is None:
        return
    try:
        await asyncio.wait_for(task, timeout=10)
    except asyncio.TimeoutError:
        logger.warning("DB keepalive task did not stop within timeout; cancelling.")
        task.cancel()
