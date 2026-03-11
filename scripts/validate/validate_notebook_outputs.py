#!/usr/bin/env python3
"""Validate notebook output/layout hygiene."""

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
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - guardrail
            failures.append(f"{path}: invalid JSON ({exc})")
            continue

        for idx, cell in enumerate(payload.get("cells", [])):
            if cell.get("cell_type") != "code":
                continue
            outputs = cell.get("outputs", [])
            execution_count = cell.get("execution_count")
            if outputs:
                failures.append(f"{path}: code cell {idx} has outputs")
            if execution_count is not None:
                failures.append(
                    f"{path}: code cell {idx} has execution_count={execution_count}"
                )

    for path in _iter_unexpected_files():
        failures.append(f"{path}: unexpected non-notebook file in notebooks directory")

    if failures:
        print("Notebook output/layout validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Notebook output/layout validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
