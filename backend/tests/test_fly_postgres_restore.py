from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODULE_PATH = ROOT / "scripts" / "db" / "fly_postgres_restore.py"
SPEC = spec_from_file_location("fly_postgres_restore", MODULE_PATH)
MODULE = module_from_spec(SPEC)
assert SPEC is not None
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

build_create_database_command = MODULE.build_create_database_command
build_drop_database_command = MODULE.build_drop_database_command
build_restore_command = MODULE.build_restore_command
build_verify_command = MODULE.build_verify_command


def test_build_drop_database_command_for_dev():
    command = build_drop_database_command("dev", "pax_tt_app", "restore_db")

    assert command[:5] == ["fly", "ssh", "console", "-a", "pax-tt-db-dev"]
    assert "DROP DATABASE IF EXISTS restore_db WITH (FORCE);" in command[6]


def test_build_create_database_command_for_prod():
    command = build_create_database_command("prod", "pax_tt_app", "restore_db")

    assert command[:5] == ["fly", "ssh", "console", "-a", "pax-tt-db-prod"]
    assert "CREATE DATABASE restore_db;" in command[6]


def test_build_restore_and_verify_commands():
    restore_command = build_restore_command("dev", "pax_tt_app", "restore_db")
    verify_command = build_verify_command("dev", "pax_tt_app", "restore_db")

    assert "psql -U pax_tt_app -d restore_db" in restore_command[6]
    assert "information_schema.tables" in verify_command[6]
