from pathlib import Path
import importlib.util
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_prod_health_alerts.py"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("run_prod_health_alerts", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules["run_prod_health_alerts"] = MODULE
SPEC.loader.exec_module(MODULE)


def test_split_csv_handles_empty_and_whitespace() -> None:
    assert MODULE._split_csv(None) == []
    assert MODULE._split_csv("") == []
    assert MODULE._split_csv(" a@example.com, b@example.com , ,c@example.com ") == [
        "a@example.com",
        "b@example.com",
        "c@example.com",
    ]


def test_render_alert_subject_includes_env_and_codes() -> None:
    snapshot = MODULE.HealthSnapshot(
        environment="prod",
        checked_at_utc="2026-03-06T21:00:00+00:00",
        release_sha="abc123",
        convention_mode_active=True,
        app_ok=False,
        db_ok=False,
        recommendation_ok=False,
        recommendation_state="degraded",
        events=[
            MODULE.AlertEvent(
                code="db_connectivity_failure",
                summary="db failed",
                details="db details",
            ),
            MODULE.AlertEvent(
                code="app_unreachable",
                summary="api failed",
                details="api details",
            ),
        ],
    )

    subject = MODULE._render_alert_subject(snapshot)
    assert "[pax-tt][prod] P0 alert" in subject
    assert "app_unreachable" in subject
    assert "db_connectivity_failure" in subject


def test_render_alert_html_contains_release_sha_and_events() -> None:
    snapshot = MODULE.HealthSnapshot(
        environment="prod",
        checked_at_utc="2026-03-06T21:00:00+00:00",
        release_sha="def456",
        convention_mode_active=True,
        app_ok=True,
        db_ok=False,
        recommendation_ok=False,
        recommendation_state="degraded",
        events=[
            MODULE.AlertEvent(
                code="recommendation_degraded",
                summary="recommendation down",
                details="missing embedding",
            )
        ],
    )

    html = MODULE._render_alert_html(snapshot)
    assert "def456" in html
    assert "recommendation_degraded" in html
    assert "missing embedding" in html
