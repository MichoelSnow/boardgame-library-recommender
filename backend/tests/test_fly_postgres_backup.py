from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODULE_PATH = ROOT / "scripts" / "db" / "fly_postgres_backup.py"
SPEC = spec_from_file_location("fly_postgres_backup", MODULE_PATH)
MODULE = module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_build_pg_dump_command_uses_selected_database_environment(monkeypatch):
    monkeypatch.setenv("FLY_DB_APP_NAME_DEV", "test-db-dev")

    command = MODULE.build_pg_dump_command("dev", "bg_lib_app", "bg_lib_recommender")

    assert command[:5] == ["fly", "ssh", "console", "-a", "test-db-dev"]
    assert "pg_dump -U bg_lib_app -d bg_lib_recommender" in command[6]
