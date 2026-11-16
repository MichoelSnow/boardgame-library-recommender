"""Small shared helpers for ingestion state and artifact handling."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path


def utc_now_iso() -> str:
    """Return the current UTC time in the ingestion state format."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def latest_file(directory: Path, pattern: str) -> Path:
    """Return the newest matching file or raise a descriptive error."""
    files = list(directory.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No files matching {pattern} found in {directory}")
    return max(files, key=lambda path: path.stat().st_mtime)
