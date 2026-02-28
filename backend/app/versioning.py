from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
DEFAULT_APP_VERSION = "0.0.0"


@lru_cache(maxsize=1)
def get_app_version() -> str:
    """Read the canonical app version from pyproject.toml."""
    try:
        lines = PYPROJECT_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return DEFAULT_APP_VERSION

    in_tool_poetry_section = False
    for raw_line in lines:
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
