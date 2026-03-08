#!/usr/bin/env python3
"""Scan notebook source and outputs for common secret patterns."""

from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
NOTEBOOKS_DIR = REPO_ROOT / "data_pipeline" / "notebooks"

# Pattern set intentionally focuses on likely credential leaks.
SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "google_api_key": re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
    "github_pat": re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    "slack_token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    "private_key": re.compile(r"-----BEGIN (RSA )?PRIVATE KEY-----"),
    "db_url_creds": re.compile(
        r"(postgres(ql)?|mysql|mongodb(\+srv)?)://[^/\s:@]+:[^@\s]+@",
        re.IGNORECASE,
    ),
    "bearer_token": re.compile(r"Authorization:\s*Bearer\s+[A-Za-z0-9\-_.=]+"),
    "password_assignment": re.compile(
        r"(?i)\b(password|passwd|pwd)\b\s*[:=]\s*['\"][^'\"]+['\"]"
    ),
}

# Expected variable names used by env-driven flows (not secrets by themselves).
SAFE_SUBSTRINGS = (
    "GOOGLE_CLIENT_SECRET",
    "BGG_PASSWORD",
    "SMOKE_TEST_PASSWORD",
    "ADMIN_PASSWORD",
    "token_path",
    "TOKEN_PATH",
)


def _iter_ipynb_files() -> list[Path]:
    return sorted(NOTEBOOKS_DIR.rglob("*.ipynb"))


def _flatten_notebook_text(payload: dict) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    for idx, cell in enumerate(payload.get("cells", [])):
        source = "".join(cell.get("source", []))
        if source:
            lines.append((idx, source))
        for output in cell.get("outputs", []):
            text = ""
            if isinstance(output.get("text"), list):
                text = "".join(output.get("text", []))
            elif isinstance(output.get("text"), str):
                text = output["text"]
            if text:
                lines.append((idx, text))
            data = output.get("data", {})
            for value in data.values():
                if isinstance(value, list):
                    output_text = "".join(value)
                elif isinstance(value, str):
                    output_text = value
                else:
                    output_text = ""
                if output_text:
                    lines.append((idx, output_text))
    return lines


def _is_safe_match(snippet: str) -> bool:
    return any(token in snippet for token in SAFE_SUBSTRINGS)


def main() -> int:
    failures: list[str] = []

    for notebook in _iter_ipynb_files():
        try:
            payload = json.loads(notebook.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - guardrail
            failures.append(f"{notebook}: invalid JSON ({exc})")
            continue

        for cell_idx, blob in _flatten_notebook_text(payload):
            for name, pattern in SECRET_PATTERNS.items():
                match = pattern.search(blob)
                if not match:
                    continue
                snippet = match.group(0)
                if _is_safe_match(snippet):
                    continue
                failures.append(
                    f"{notebook}: cell {cell_idx} matched {name}: {snippet[:120]}"
                )

    if failures:
        print("Notebook secret scan failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Notebook secret scan passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
