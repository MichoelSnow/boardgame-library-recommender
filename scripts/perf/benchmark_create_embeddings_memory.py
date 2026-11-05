#!/usr/bin/env python3
"""Measure create_embeddings memory use on deterministic DuckDB samples."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import duckdb


DEFAULT_SAMPLES = (0.5, 1.0, 2.5, 5.0, 10.0, 20.0)
DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_MAX_MEMORY_MB = 2048


def _latest_ratings_db(ratings_dir: Path) -> Path:
    candidates = sorted(ratings_dir.glob("boardgame_ratings_*.duckdb"))
    if not candidates:
        raise FileNotFoundError(f"No ratings DuckDB files found in {ratings_dir}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _duckdb_string_literal(path: Path) -> str:
    """Return a filesystem path quoted as a DuckDB SQL string literal."""

    return "'" + str(path.resolve()).replace("'", "''") + "'"


def _sample_database(
    source: Path, destination: Path, percentage: float
) -> dict[str, int]:
    threshold = int(round(percentage * 100))
    # The connection must be writable so DuckDB can create the new attached
    # sample database. The source itself is only queried; all writes target
    # the temporary database.
    with duckdb.connect(str(source)) as source_connection:
        source_connection.execute("SELECT 1 FROM boardgame_ratings LIMIT 1").fetchone()
        source_connection.execute(
            f"ATTACH {_duckdb_string_literal(destination)} AS sample_db"
        )
        source_connection.execute(
            """
            CREATE TABLE sample_db.boardgame_ratings AS
            SELECT game_id, rating_round, username
            FROM boardgame_ratings
            WHERE hash(game_id) % 10000 < ?
            """,
            [threshold],
        )
        source_connection.execute("DETACH sample_db")
    with duckdb.connect(str(destination), read_only=True) as destination_connection:
        row_count, game_count, user_count = destination_connection.execute(
            """
            SELECT count(*), count(DISTINCT game_id), count(DISTINCT username)
            FROM boardgame_ratings
            """
        ).fetchone()
    return {
        "rows": int(row_count),
        "games": int(game_count),
        "users": int(user_count),
    }


def _rss_bytes(pid: int) -> int:
    try:
        status = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
    except (FileNotFoundError, PermissionError):
        return 0
    for line in status.splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) * 1024
    return 0


def _terminate_process_group(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def _run_worker(
    sample_db: Path, timeout_seconds: int, max_memory_mb: int
) -> dict[str, object]:
    command = [sys.executable, __file__, "--worker", str(sample_db)]
    process = subprocess.Popen(
        command,
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    started = time.monotonic()
    memory_limit = max_memory_mb * 1024 * 1024
    exceeded_memory = False
    timed_out = False
    while process.poll() is None:
        if _rss_bytes(process.pid) > memory_limit:
            exceeded_memory = True
            _terminate_process_group(process)
            break
        if time.monotonic() - started >= timeout_seconds:
            timed_out = True
            _terminate_process_group(process)
            break
        time.sleep(0.25)

    stdout, stderr = process.communicate()
    elapsed = time.monotonic() - started
    result: dict[str, object] = {
        "elapsed_seconds": round(elapsed, 2),
        "exit_code": process.returncode,
        "peak_rss_mb": None,
        "status": "success",
    }
    if exceeded_memory:
        result["status"] = "memory_limit_exceeded"
    elif timed_out:
        result["status"] = "timeout"
    elif process.returncode != 0:
        result["status"] = "failed"
    try:
        worker_result = json.loads(stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        worker_result = {}
    result.update(worker_result)
    if stderr.strip():
        result["stderr_tail"] = stderr.strip().splitlines()[-10:]
    return result


def _worker(sample_db: Path) -> int:
    import resource

    from data_pipeline.src.features.create_embeddings import GameRecommender

    recommender = GameRecommender(min_ratings_per_user=3)
    recommender.fit_from_duckdb(sample_db)
    print(
        json.dumps(
            {
                "games": int(recommender.game_embeddings.shape[0]),
                "users": int(recommender.rating_matrix.shape[0]),
                "nonzero": int(recommender.rating_matrix.nnz),
                "peak_rss_mb": round(
                    resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2
                ),
            }
        )
    )
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ratings-db", type=Path)
    parser.add_argument("--samples", default=",".join(map(str, DEFAULT_SAMPLES)))
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--max-memory-mb", type=int, default=DEFAULT_MAX_MEMORY_MB)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--keep-samples", action="store_true")
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.worker:
        return _worker(args.worker)
    if args.timeout_seconds <= 0 or args.max_memory_mb <= 0:
        raise ValueError("Timeout and memory limit must be positive")

    project_root = Path(__file__).resolve().parents[2]
    source = args.ratings_db or _latest_ratings_db(
        project_root / "data" / "ingest" / "ratings"
    )
    percentages = [float(value) for value in args.samples.split(",")]
    report_path = (
        args.report
        or project_root / "logs" / "profiling" / "create_embeddings_memory.jsonl"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    sample_dir = report_path.parent / f".create_embeddings_samples_{os.getpid()}"
    sample_dir.mkdir(parents=True, exist_ok=True)

    with report_path.open("a", encoding="utf-8") as report:
        for percentage in percentages:
            if not 0 < percentage <= 100:
                raise ValueError(
                    "Sample percentages must be greater than 0 and at most 100"
                )
            sample_db = sample_dir / f"sample_{percentage:g}.duckdb"
            counts = _sample_database(source, sample_db, percentage)
            result = _run_worker(sample_db, args.timeout_seconds, args.max_memory_mb)
            record = {
                "source": str(source),
                "sample_percent": percentage,
                "timeout_seconds": args.timeout_seconds,
                "max_memory_mb": args.max_memory_mb,
                **counts,
                **result,
            }
            report.write(json.dumps(record) + "\n")
            report.flush()
            if result["status"] != "success":
                break
    if not args.keep_samples:
        for sample_db in sample_dir.glob("*.duckdb"):
            sample_db.unlink()
        sample_dir.rmdir()
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
