#!/usr/bin/env python3

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

MAX_RSS_PATTERN = re.compile(r"Maximum resident set size \(kbytes\):\s*(\d+)")
TIME_VERBOSE_PATTERNS = {
    "user_time_seconds": re.compile(r"User time \(seconds\):\s*([0-9.]+)"),
    "system_time_seconds": re.compile(r"System time \(seconds\):\s*([0-9.]+)"),
    "cpu_percent": re.compile(r"Percent of CPU this job got:\s*([0-9]+)%"),
    "elapsed_wall_time": re.compile(
        r"Elapsed \(wall clock\) time \(h:mm:ss or m:ss\):\s*([0-9:.]+)"
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Profile an ingest-stage command with `time -v` and write JSON to logs."
        )
    )
    parser.add_argument(
        "--target-functions",
        required=True,
        help="Comma-separated function/stage names being profiled.",
    )
    parser.add_argument(
        "--output-dir",
        default="logs/profiling/data_pipeline",
        help="Output directory for profile artifacts.",
    )
    parser.add_argument(
        "--max-output-chars",
        type=int,
        default=2000,
        help="Maximum stdout/stderr chars stored in output JSON.",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command to execute. Prefix with --, e.g. -- poetry run ...",
    )
    return parser.parse_args()


def _sanitize_command(command: list[str]) -> list[str]:
    if not command:
        raise ValueError("No command provided. Use -- <command> ...")
    if command[0] == "--":
        command = command[1:]
    if not command:
        raise ValueError("No command provided after --.")
    return command


def _parse_target_functions(raw: str) -> list[str]:
    values = [v.strip() for v in raw.split(",")]
    functions = [v for v in values if v]
    if not functions:
        raise ValueError("--target-functions must contain at least one function name.")
    return functions


def _safe_filename_token(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", value.strip())
    return safe.strip("_") or "unknown"


def _short_target_name(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return "unknown"
    parts = stripped.split(".")
    if parts[-1] == "main" and len(parts) >= 2:
        return parts[-2]
    return parts[-1]


def extract_max_rss_kb(stderr_text: str) -> int | None:
    match = MAX_RSS_PATTERN.search(stderr_text)
    if not match:
        return None
    return int(match.group(1))


def extract_time_verbose_metrics(stderr_text: str) -> dict[str, str]:
    metrics: dict[str, str] = {}
    for key, pattern in TIME_VERBOSE_PATTERNS.items():
        match = pattern.search(stderr_text)
        if match:
            metrics[key] = match.group(1)
    return metrics


def run_profiled_command(command: list[str]) -> dict[str, Any]:
    time_bin = shutil.which("time")
    if time_bin is None:
        raise RuntimeError("Could not find 'time' executable on PATH.")

    started = time.perf_counter()
    started_utc = datetime.now(timezone.utc).isoformat()
    completed = subprocess.run(
        [time_bin, "-v", *command],
        capture_output=True,
        text=True,
        check=False,
    )
    duration_seconds = time.perf_counter() - started

    return {
        "started_at_utc": started_utc,
        "duration_seconds": round(duration_seconds, 3),
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "max_rss_kb": extract_max_rss_kb(completed.stderr),
        "time_verbose_metrics": extract_time_verbose_metrics(completed.stderr),
    }


def write_result(
    *,
    target_functions: list[str],
    command: list[str],
    output_dir: Path,
    run_data: dict[str, Any],
    max_output_chars: int,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    primary_function = _safe_filename_token(_short_target_name(target_functions[0]))
    output_path = output_dir / f"{primary_function}.{timestamp}.json"
    payload = {
        "target_functions": target_functions,
        "profile_generator_function": "scripts.data_pipeline.profile_ingest_stage.run_profiled_command",
        "command": command,
        "started_at_utc": run_data["started_at_utc"],
        "duration_seconds": run_data["duration_seconds"],
        "exit_code": run_data["exit_code"],
        "max_rss_kb": run_data["max_rss_kb"],
        "time_verbose_metrics": run_data["time_verbose_metrics"],
        "stdout_tail": run_data["stdout"][-max_output_chars:],
        "stderr_tail": run_data["stderr"][-max_output_chars:],
    }
    payload["tails_pretty_lines"] = [
        "=== STDOUT TAIL ===",
        *payload["stdout_tail"].splitlines(),
        "",
        "=== STDERR TAIL ===",
        *payload["stderr_tail"].splitlines(),
    ]
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_path


def main() -> int:
    args = parse_args()
    try:
        command = _sanitize_command(args.command)
        target_functions = _parse_target_functions(args.target_functions)
    except ValueError as exc:
        logger.error(str(exc))
        return 2

    run_data = run_profiled_command(command)
    output_path = write_result(
        target_functions=target_functions,
        command=command,
        output_dir=Path(args.output_dir),
        run_data=run_data,
        max_output_chars=max(args.max_output_chars, 0),
    )

    logger.info("Profiling result written to %s", output_path)
    logger.info(
        "target_functions=%s exit_code=%s duration_seconds=%s max_rss_kb=%s",
        ",".join(target_functions),
        run_data["exit_code"],
        run_data["duration_seconds"],
        run_data["max_rss_kb"],
    )
    return 0 if run_data["exit_code"] == 0 else run_data["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
