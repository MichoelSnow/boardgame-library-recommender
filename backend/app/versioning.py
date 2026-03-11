from functools import lru_cache
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None
    try:
        import tomli
    except ModuleNotFoundError:
        tomli = None
else:
    tomli = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
DEFAULT_APP_VERSION = "0.0.0"


def _parse_version_from_pyproject_text(pyproject_text: str) -> str:
    parser = tomllib or tomli
    if parser is not None:
        try:
            pyproject_data = parser.loads(pyproject_text)
        except Exception:
            pyproject_data = None
        else:
            version = pyproject_data.get("tool", {}).get("poetry", {}).get("version")
            if isinstance(version, str) and version.strip():
                return version.strip()

    in_tool_poetry_section = False
    for raw_line in pyproject_text.splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if line.startswith("[") and line.endswith("]"):
            in_tool_poetry_section = line == "[tool.poetry]"
            continue

        if in_tool_poetry_section and line.startswith("version"):
            _, _, value = line.partition("=")
            version = value.strip().strip('"').strip("'")
            return version or DEFAULT_APP_VERSION

    return DEFAULT_APP_VERSION


@lru_cache(maxsize=1)
def get_app_version() -> str:
    """Read the canonical app version from pyproject.toml."""
    try:
        pyproject_text = PYPROJECT_PATH.read_text(encoding="utf-8")
    except OSError:
        return DEFAULT_APP_VERSION

    return _parse_version_from_pyproject_text(pyproject_text)
