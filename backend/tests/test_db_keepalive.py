import asyncio
import pytest

from backend.app.db_keepalive import (
    resolve_keepalive_interval_seconds,
    run_db_keepalive_loop,
    should_enable_db_keepalive,
)


def test_should_enable_db_keepalive_enabled_for_postgres_by_default() -> None:
    assert should_enable_db_keepalive("postgresql://u:p@localhost/db", {}) is True


def test_should_enable_db_keepalive_disabled_for_sqlite() -> None:
    assert should_enable_db_keepalive("sqlite:////tmp/test.db", {}) is False


def test_should_enable_db_keepalive_explicit_disable() -> None:
    env = {"DB_KEEPALIVE_ENABLED": "false"}
    assert should_enable_db_keepalive("postgresql://u:p@localhost/db", env) is False


def test_resolve_keepalive_interval_default() -> None:
    assert resolve_keepalive_interval_seconds({}) == 60


def test_resolve_keepalive_interval_custom() -> None:
    assert resolve_keepalive_interval_seconds({"DB_KEEPALIVE_INTERVAL_SECONDS": "120"}) == 120


def test_resolve_keepalive_interval_rejects_invalid() -> None:
    with pytest.raises(RuntimeError, match="positive integer"):
        resolve_keepalive_interval_seconds({"DB_KEEPALIVE_INTERVAL_SECONDS": "abc"})


def test_resolve_keepalive_interval_rejects_too_small() -> None:
    with pytest.raises(RuntimeError, match=">= 5 seconds"):
        resolve_keepalive_interval_seconds({"DB_KEEPALIVE_INTERVAL_SECONDS": "2"})


def test_run_db_keepalive_loop_invokes_ping(monkeypatch: pytest.MonkeyPatch) -> None:
    async def runner() -> None:
        stop_event = asyncio.Event()
        calls: list[int] = []

        async def fake_to_thread(fn, *args):  # type: ignore[no-untyped-def]
            fn(*args)

        def fake_ping(_: object) -> None:
            calls.append(1)
            stop_event.set()

        monkeypatch.setattr("backend.app.db_keepalive.asyncio.to_thread", fake_to_thread)

        await asyncio.wait_for(
            run_db_keepalive_loop(
                engine=object(),  # type: ignore[arg-type]
                interval_seconds=60,
                stop_event=stop_event,
                ping_fn=fake_ping,
            ),
            timeout=1,
        )
        assert calls == [1]

    asyncio.run(runner())


def test_run_db_keepalive_loop_respects_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    async def runner() -> None:
        stop_event = asyncio.Event()

        async def fake_to_thread(fn, *args):  # type: ignore[no-untyped-def]
            await asyncio.sleep(10)

        monkeypatch.setattr("backend.app.db_keepalive.asyncio.to_thread", fake_to_thread)

        def fake_ping(_: object) -> None:
            return

        task = asyncio.create_task(
            run_db_keepalive_loop(
                engine=object(),  # type: ignore[arg-type]
                interval_seconds=60,
                stop_event=stop_event,
                ping_fn=fake_ping,
            )
        )
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(runner())
