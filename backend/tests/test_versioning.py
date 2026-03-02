from pathlib import Path

from backend.app.versioning import DEFAULT_APP_VERSION, get_app_version


def _read_pyproject_version() -> str:
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    for raw_line in pyproject_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("version = "):
            return line.split("=", 1)[1].strip().strip('"')
    raise AssertionError("Could not find version in pyproject.toml")


def test_get_app_version_matches_pyproject():
    get_app_version.cache_clear()

    version = get_app_version()

    assert version == _read_pyproject_version()
    assert version != DEFAULT_APP_VERSION
