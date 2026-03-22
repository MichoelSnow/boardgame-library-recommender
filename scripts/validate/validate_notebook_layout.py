#!/usr/bin/env python3
"""Validate notebook JSON and notebook-directory file layout."""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
NOTEBOOKS_DIR = REPO_ROOT / "data_pipeline" / "notebooks"
ALLOWED_NON_NOTEBOOK_FILES = {
    NOTEBOOKS_DIR / "README.md",
    NOTEBOOKS_DIR / "archive" / "README.md",
}


def _iter_ipynb_files() -> list[Path]:
    return sorted(NOTEBOOKS_DIR.rglob("*.ipynb"))


def _iter_unexpected_files() -> list[Path]:
    unexpected: list[Path] = []
    for path in NOTEBOOKS_DIR.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix == ".ipynb":
            continue
        if path in ALLOWED_NON_NOTEBOOK_FILES:
            continue
        unexpected.append(path)
    return sorted(unexpected)


def main() -> int:
    failures: list[str] = []

    for path in _iter_ipynb_files():
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - guardrail
            failures.append(f"{path}: invalid JSON ({exc})")

    for path in _iter_unexpected_files():
        failures.append(f"{path}: unexpected non-notebook file in notebooks directory")

    if failures:
        print("Notebook JSON/layout validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Notebook JSON/layout validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
