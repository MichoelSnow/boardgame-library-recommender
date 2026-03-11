from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODULE_PATH = (
    ROOT / "scripts" / "db" / "fly_postgres_backup.py"
)
SPEC = spec_from_file_location("fly_postgres_backup", MODULE_PATH)
MODULE = module_from_spec(SPEC)
assert SPEC is not None
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

build_default_output_path = MODULE.build_default_output_path
build_pg_dump_command = MODULE.build_pg_dump_command


def test_build_pg_dump_command_for_dev():
    command = build_pg_dump_command("dev", "pax_tt_app", "pax_tt_recommender")

    assert command[:5] == ["fly", "ssh", "console", "-a", "pax-tt-db-dev"]
    assert command[5] == "-C"
    assert "pg_dump -U pax_tt_app -d pax_tt_recommender" in command[6]
    assert "--clean --if-exists --no-owner --no-privileges" in command[6]


def test_build_default_output_path_uses_environment_and_sql_suffix():
    path = build_default_output_path("prod", output_dir="/tmp")

    assert isinstance(path, Path)
    assert path.parent == Path("/tmp")
    assert path.name.startswith("pax-tt-prod-postgres-backup-")
    assert path.suffix == ".sql"
