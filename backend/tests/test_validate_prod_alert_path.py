from pathlib import Path
import importlib.util
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "validate" / "validate_prod_alert_path.py"
sys.path.insert(0, str(REPO_ROOT))
SPEC = importlib.util.spec_from_file_location("validate_prod_alert_path", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules["validate_prod_alert_path"] = MODULE
SPEC.loader.exec_module(MODULE)


def test_static_constants_match_expected_values() -> None:
    assert MODULE.EXPECTED_CRON == 'cron: "*/20 * * * *"'
    assert (
        MODULE.EXPECTED_RUN_COMMAND
        == "python scripts/alerts/run_prod_health_alerts.py --env prod"
    )


def test_paths_point_to_expected_files() -> None:
    assert MODULE.WORKFLOW_PATH.as_posix() == ".github/workflows/prod-health-alerts.yml"
    assert (
        MODULE.ALERT_SCRIPT_PATH.as_posix()
        == "scripts/alerts/run_prod_health_alerts.py"
    )
