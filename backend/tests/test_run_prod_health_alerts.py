import importlib.util
from pathlib import Path
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


def test_alert_runner_returns_failure_for_unhealthy_snapshot(monkeypatch):
    snapshot = MODULE.HealthSnapshot(
        environment="prod",
        checked_at_utc="2026-03-07T00:00:00+00:00",
        release_sha="def456",
        convention_mode_active=True,
        app_ok=False,
        db_ok=False,
        recommendation_ok=False,
        recommendation_state="degraded",
        api_latency_ms=2000.0,
        api_version_latency_ms=2100.0,
        recommendations_latency_ms=5000.0,
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
            state_path=".alert_state/test_failure.json",
            cooldown_seconds=0,
        ),
    )
    monkeypatch.setattr(MODULE, "load_alert_state", lambda _path: {})
    monkeypatch.setattr(MODULE, "save_alert_state", lambda _path, _payload: None)

    assert MODULE.main() == 1
