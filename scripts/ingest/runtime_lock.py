#!/usr/bin/env python3
"""Create and release the shared ingestion workspace ownership record."""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_LOCK_PATH = "/app/data/ingest/run_owner.json"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _lock_path() -> Path:
    return Path(os.getenv("INGEST_LOCK_PATH", DEFAULT_LOCK_PATH))


def _run_id() -> str:
    return os.getenv("INGEST_RUN_ID", "").strip() or str(uuid.uuid4())


def _metadata() -> dict[str, Any]:
    return {
        "run_id": _run_id(),
        "target": os.getenv("INGEST_TARGET", "unspecified"),
        "runtime_name": os.getenv("INGEST_RUNTIME_NAME", "unknown"),
        "image_git_sha": os.getenv("APP_GIT_SHA", "unknown"),
        "image_build_timestamp": os.getenv("APP_BUILD_TIMESTAMP", "unknown"),
        "workspace": os.getenv("INGEST_WORKSPACE", "/app/data"),
        "host": socket.gethostname(),
        "started_at_utc": _now(),
    }


def _read(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to read ownership record {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"Ownership record {path} is not a JSON object")
    return value


def acquire(path: Path | None = None) -> dict[str, Any]:
    lock_path = path or _lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    record = _metadata()
    try:
        descriptor = os.open(
            lock_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError as exc:
        existing = _read(lock_path)
        details = json.dumps(existing, sort_keys=True) if existing else "unknown"
        raise RuntimeError(
            f"Ingestion workspace is already owned; inspect {lock_path}: {details}"
        ) from exc

    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except Exception:
        lock_path.unlink(missing_ok=True)
        raise
    return record


def release(path: Path | None = None) -> None:
    lock_path = path or _lock_path()
    record = _read(lock_path)
    if record is None:
        return
    current_run_id = _run_id()
    if record.get("run_id") != current_run_id:
        raise RuntimeError(
            f"Ownership record {lock_path} belongs to run "
            f"{record.get('run_id', 'unknown')}, not {current_run_id}"
        )
    lock_path.unlink()


def clear(path: Path | None = None, *, force: bool = False) -> None:
    if not force:
        raise RuntimeError("Clearing ownership requires --force after checking status")
    lock_path = path or _lock_path()
    lock_path.unlink(missing_ok=True)


def show(path: Path | None = None) -> dict[str, Any] | None:
    return _read(path or _lock_path())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("acquire", "release", "clear", "show"),
    )
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "acquire":
            print(json.dumps(acquire(), indent=2, sort_keys=True))
        elif args.command == "release":
            release()
        elif args.command == "clear":
            clear(force=args.force)
        elif args.command == "show":
            record = show()
            if record is not None:
                print(json.dumps(record, indent=2, sort_keys=True))
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
