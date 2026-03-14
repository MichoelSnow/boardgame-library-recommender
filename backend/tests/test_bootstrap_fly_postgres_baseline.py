from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODULE_PATH = ROOT / "scripts" / "db" / "bootstrap_fly_postgres_baseline.py"
SPEC = spec_from_file_location("bootstrap_fly_postgres_baseline", MODULE_PATH)
MODULE = module_from_spec(SPEC)
assert SPEC is not None
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

resolve_env_values = MODULE.resolve_env_values
validate_db_identifier = MODULE.validate_db_identifier
format_command_for_log = MODULE.format_command_for_log


def test_validate_db_identifier_accepts_safe_identifiers():
    assert validate_db_identifier("boardgame_recommender") == "boardgame_recommender"


def test_validate_db_identifier_rejects_unsafe_identifiers():
    with pytest.raises(ValueError):
        validate_db_identifier("boardgame-recommender")


def test_resolve_env_values_for_dev(monkeypatch):
    monkeypatch.setenv("FLY_DB_APP_NAME_DEV", "db-dev")
    monkeypatch.setenv("FLY_APP_NAME_DEV", "app-dev")
    monkeypatch.setenv("POSTGRES_PASSWORD_DEV", "pw-dev")
    monkeypatch.setenv("POSTGRES_DB", "boardgame_recommender")

    values = resolve_env_values("dev", None)

    assert values["db_app_name"] == "db-dev"
    assert values["app_name"] == "app-dev"
    assert values["password"] == "pw-dev"
    assert values["postgres_db"] == "boardgame_recommender"


def test_format_command_for_log_redacts_postgres_url_password():
    command = [
        "fly",
        "ssh",
        "console",
        "-a",
        "db-app",
        "-C",
        'psql "postgresql://postgres:supersecret@127.0.0.1:5432/postgres" -c "SELECT 1;"',
    ]
    rendered = format_command_for_log(command)
    assert "supersecret" not in rendered
    assert "postgresql://postgres:***@127.0.0.1:5432/postgres" in rendered
