from pathlib import Path
import importlib.util
import sys


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
    monkeypatch.setattr(MODULE, "parse_args", lambda: MODULE.argparse.Namespace(env="prod", dry_run=False))
    assert MODULE.main() == 0


def test_main_returns_zero_when_no_alert_conditions(monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "check_prod_health", lambda _: _healthy_snapshot(True))
    monkeypatch.setattr(MODULE, "parse_args", lambda: MODULE.argparse.Namespace(env="prod", dry_run=False))
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
    monkeypatch.setattr(MODULE, "parse_args", lambda: MODULE.argparse.Namespace(env="prod", dry_run=False))
    assert MODULE.main() == 1
