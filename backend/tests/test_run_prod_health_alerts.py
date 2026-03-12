from pathlib import Path
import importlib.util
import sys
from datetime import datetime, timezone
import logging


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "alerts" / "run_prod_health_alerts.py"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("run_prod_health_alerts", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules["run_prod_health_alerts"] = MODULE
SPEC.loader.exec_module(MODULE)


def _healthy_snapshot(convention_mode_active: bool = True) -> MODULE.HealthSnapshot:
    return MODULE.HealthSnapshot(
        environment="prod",
        checked_at_utc="2026-03-07T00:00:00+00:00",
        release_sha="abc123",
        convention_mode_active=convention_mode_active,
        app_ok=True,
        db_ok=True,
        recommendation_ok=True,
        recommendation_state="healthy",
        events=[],
    )


def test_main_returns_zero_when_convention_mode_is_off(monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "check_prod_health", lambda _: _healthy_snapshot(False))
    monkeypatch.setattr(
        MODULE,
        "parse_args",
        lambda: MODULE.argparse.Namespace(
            env="prod",
            dry_run=False,
            state_path=".alert_state/test_off.json",
            cooldown_seconds=0,
        ),
    )
    assert MODULE.main() == 0


def test_main_returns_zero_when_no_alert_conditions(monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "check_prod_health", lambda _: _healthy_snapshot(True))
    monkeypatch.setattr(
        MODULE,
        "parse_args",
        lambda: MODULE.argparse.Namespace(
            env="prod",
            dry_run=False,
            state_path=".alert_state/test_no_alerts.json",
            cooldown_seconds=0,
        ),
    )
    monkeypatch.setattr(MODULE, "load_alert_state", lambda _path: {})
    monkeypatch.setattr(MODULE, "save_alert_state", lambda _path, _payload: None)
    assert MODULE.main() == 0


def test_main_returns_one_on_alert_conditions(monkeypatch) -> None:
    snapshot = MODULE.HealthSnapshot(
        environment="prod",
        checked_at_utc="2026-03-07T00:00:00+00:00",
        release_sha="def456",
        convention_mode_active=True,
        app_ok=False,
        db_ok=False,
        recommendation_ok=False,
        recommendation_state="degraded",
        events=[
            MODULE.AlertEvent(
                code="app_unreachable",
                summary="api failed",
                details="connection timeout",
            )
        ],
    )
    monkeypatch.setattr(MODULE, "check_prod_health", lambda _: snapshot)
    monkeypatch.setattr(
        MODULE,
        "parse_args",
        lambda: MODULE.argparse.Namespace(
            env="prod",
            dry_run=False,
            state_path=".alert_state/test_main_returns_one.json",
            cooldown_seconds=0,
        ),
    )
    monkeypatch.setattr(MODULE, "load_alert_state", lambda _path: {})
    monkeypatch.setattr(MODULE, "save_alert_state", lambda _path, _payload: None)
    assert MODULE.main() == 1


def test_filter_alert_events_transition_and_cooldown() -> None:
    snapshot = MODULE.HealthSnapshot(
        environment="prod",
        checked_at_utc="2026-03-07T00:00:00+00:00",
        release_sha="sha1",
        convention_mode_active=True,
        app_ok=True,
        db_ok=True,
        recommendation_ok=False,
        recommendation_state="degraded",
        events=[
            MODULE.AlertEvent(
                code="recommendation_degraded",
                summary="Recommendation subsystem reported degraded mode",
                details="{}",
            )
        ],
    )

    now_utc = datetime(2026, 3, 7, 0, 0, 0, tzinfo=timezone.utc)

    transitioned = MODULE.filter_alert_events(
        snapshot=snapshot,
        previous_state={
            "last_recommendation_state": "ready",
            "last_emitted_at_utc_by_code": {},
        },
        now_utc=now_utc,
        cooldown_seconds=3600,
    )
    assert len(transitioned) == 1
    assert transitioned[0].code == "recommendation_degraded"

    suppressed = MODULE.filter_alert_events(
        snapshot=snapshot,
        previous_state={
            "last_recommendation_state": "degraded",
            "last_emitted_at_utc_by_code": {
                "recommendation_degraded": "2026-03-06T23:30:00+00:00"
            },
        },
        now_utc=now_utc,
        cooldown_seconds=3600,
    )
    assert suppressed == []


def test_load_alert_state_logs_and_recovers_on_invalid_json(
    tmp_path: Path, caplog
) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text("{invalid-json", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        loaded = MODULE.load_alert_state(state_path)

    assert loaded == {}
    assert "Failed to load alert state" in caplog.text


def test_save_alert_state_logs_and_recovers_on_write_failure(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    state_path = tmp_path / "state.json"

    def _raise_on_replace(self: Path, target: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(Path, "replace", _raise_on_replace)

    with caplog.at_level(logging.WARNING):
        MODULE.save_alert_state(state_path, {"k": "v"})

    assert "Failed to persist alert state" in caplog.text
