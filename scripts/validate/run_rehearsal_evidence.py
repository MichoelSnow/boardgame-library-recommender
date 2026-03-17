#!/usr/bin/env python3

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import logging
import math
import os
from pathlib import Path
import statistics
import subprocess
import time
import urllib.error
import urllib.request
from typing import Any

from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

try:
    from validation_common import build_url, load_dotenv
except ModuleNotFoundError:
    from scripts.validation_common import build_url, load_dotenv

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_GAME_ID = 224517
DEFAULT_LATENCY_SAMPLES = 120
DEFAULT_MEMORY_INTERVAL_SECONDS = 0
DEFAULT_MEMORY_LOAD_REQUESTS = 120
DEFAULT_MEMORY_LOAD_CONCURRENCY = 8
DEFAULT_READY_TIMEOUT_SECONDS = 300


def _is_retryable_http_error(exc: BaseException) -> bool:
    if not isinstance(exc, urllib.error.HTTPError):
        return False
    return exc.code == 429 or 500 <= exc.code <= 599


@retry(
    retry=retry_if_exception(_is_retryable_http_error)
    | retry_if_exception(lambda exc: isinstance(exc, urllib.error.URLError)),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
)
def request_bytes(url: str, *, timeout_seconds: int = 20) -> bytes:
    request = urllib.request.Request(url=url, method="GET")
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.read()


def run_command(
    command: list[str],
    *,
    output_path: Path | None = None,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    logger.info("Running: %s", " ".join(command))
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    combined = f"{result.stdout}{result.stderr}"
    if output_path is not None:
        output_path.write_text(combined, encoding="utf-8")
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(command)}\n{combined}"
        )
    return result


def get_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def collect_latency_measurements(
    *,
    environment: str,
    game_id: int,
    samples: int,
    output_path: Path,
) -> None:
    endpoints = [
        "/api",
        "/api/version",
        "/api/games/?limit=24&skip=0&sort_by=rank",
        f"/api/recommendations/{game_id}?limit=24",
    ]

    metrics: dict[str, Any] = {}
    for endpoint in endpoints:
        url = build_url(environment, endpoint)
        values: list[float] = []
        logger.info("Measuring latency for %s (%s samples)", endpoint, samples)
        for _ in range(samples):
            started = time.perf_counter()
            _ = request_bytes(url)
            values.append((time.perf_counter() - started) * 1000)

        values_sorted = sorted(values)
        p95 = values_sorted[math.ceil(0.95 * len(values_sorted)) - 1]
        metrics[endpoint] = {
            "samples": samples,
            "p50_ms": round(statistics.median(values), 2),
            "p95_ms": round(p95, 2),
            "max_ms": round(max(values), 2),
        }

    output_path.write_text(
        json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8"
    )
    logger.info("Wrote latency measurements to %s", output_path)


def capture_memory_snapshot(*, app_name: str, output_path: Path) -> None:
    remote_command = (
        "sh -lc 'for p in /proc/[0-9]*; do "
        '[ -r "$p/cmdline" ] || continue; '
        'cmd=$(tr "\\000" " " < "$p/cmdline" 2>/dev/null || true); '
        'case "$cmd" in *"for p in /proc/[0-9]*"*) continue ;; esac; '
        'case "$cmd" in '
        "*gunicorn*|*uvicorn*) "
        'pid=${p#/proc/}; ppid="?"; rss_kb="0"; '
        'if [ -r "$p/status" ]; then '
        'while IFS=":" read -r key value; do '
        'case "$key" in '
        'PPid) ppid=$(echo "$value" | tr -d "[:space:]") ;; '
        'VmRSS) rss_kb=$(echo "$value" | tr -cd "0-9") ;; '
        "esac; "
        'done < "$p/status"; '
        "fi; "
        'printf "%s %s %s %s\\n" "$pid" "$ppid" "$rss_kb" "$cmd" ;; '
        "esac; "
        "done | sort -n'"
    )
    run_command(
        ["fly", "ssh", "console", "-a", app_name, "-C", remote_command],
        output_path=output_path,
    )


def run_memory_active_load(
    *,
    environment: str,
    game_id: int,
    requests_per_endpoint: int,
    concurrency: int,
    output_path: Path,
) -> None:
    endpoints = [
        "/api/games/?limit=24&skip=0&sort_by=rank&library_only=true",
        f"/api/recommendations/{game_id}?limit=24",
    ]
    urls = [build_url(environment, endpoint) for endpoint in endpoints]
    jobs: list[str] = []
    for _ in range(max(requests_per_endpoint, 1)):
        jobs.extend(urls)

    logger.info(
        "Running active memory load (%s requests x %s endpoints, concurrency=%s).",
        requests_per_endpoint,
        len(endpoints),
        max(concurrency, 1),
    )
    started = time.perf_counter()
    successes = 0
    failures = 0
    failure_examples: list[str] = []

    def _hit(url: str) -> None:
        _ = request_bytes(url)

    with ThreadPoolExecutor(max_workers=max(concurrency, 1)) as executor:
        futures = [executor.submit(_hit, url) for url in jobs]
        for future in as_completed(futures):
            try:
                future.result()
                successes += 1
            except Exception as exc:
                failures += 1
                if len(failure_examples) < 10:
                    failure_examples.append(str(exc))

    duration_seconds = round(time.perf_counter() - started, 2)
    summary = {
        "environment": environment,
        "game_id": game_id,
        "requests_per_endpoint": requests_per_endpoint,
        "endpoint_count": len(endpoints),
        "total_requests": len(jobs),
        "concurrency": max(concurrency, 1),
        "successes": successes,
        "failures": failures,
        "duration_seconds": duration_seconds,
        "failure_examples": failure_examples,
    }
    output_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    logger.info("Wrote active-load summary to %s", output_path)
    if failures:
        logger.warning("Active memory load had %s failed requests.", failures)


def wait_until_ready(*, app_name: str, timeout_seconds: int) -> int:
    url = f"https://{app_name}.fly.dev/health/ready"
    started = time.monotonic()
    while True:
        try:
            _ = request_bytes(url, timeout_seconds=15)
            return int(time.monotonic() - started)
        except Exception:
            if time.monotonic() - started >= timeout_seconds:
                raise RuntimeError(f"Timed out waiting for readiness at {url}")
            time.sleep(2)


def measure_restart_timing(
    *,
    app_name: str,
    output_path: Path,
    trials: int,
    ready_timeout_seconds: int,
) -> None:
    machine_list = run_command(
        ["fly", "machine", "list", "-a", app_name, "--json"],
        check=True,
    )
    machines = json.loads(machine_list.stdout)
    if not machines:
        raise RuntimeError(f"No machines found for app {app_name}")
    machine_id = str(machines[0]["id"])

    lines: list[str] = []
    for trial in range(1, trials + 1):
        run_command(
            ["fly", "machine", "restart", "-a", app_name, machine_id],
            check=True,
        )
        ready_in_seconds = wait_until_ready(
            app_name=app_name,
            timeout_seconds=ready_timeout_seconds,
        )
        lines.append(f"trial={trial} ready_in_seconds={ready_in_seconds}")
        logger.info("Restart trial %s ready in %ss", trial, ready_in_seconds)

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote startup/restart timing to %s", output_path)


def write_summary(*, evidence_dir: Path, files: list[str]) -> None:
    summary_path = evidence_dir / "README.txt"
    lines = [
        "Rehearsal evidence bundle",
        f"Generated: {datetime.now(timezone.utc).replace(microsecond=0).isoformat()}",
        f"Dir: {evidence_dir}",
        "",
        "Key files:",
        *[f"- {name}" for name in files],
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run pre-convention rehearsal evidence collection in one command."
    )
    parser.add_argument("--env", choices=["dev"], default="dev")
    parser.add_argument("--game-id", type=int, default=DEFAULT_GAME_ID)
    parser.add_argument("--latency-samples", type=int, default=DEFAULT_LATENCY_SAMPLES)
    parser.add_argument(
        "--memory-interval-seconds", type=int, default=DEFAULT_MEMORY_INTERVAL_SECONDS
    )
    parser.add_argument(
        "--memory-load-requests",
        type=int,
        default=DEFAULT_MEMORY_LOAD_REQUESTS,
        help="Requests per endpoint during active memory load phase.",
    )
    parser.add_argument(
        "--memory-load-concurrency",
        type=int,
        default=DEFAULT_MEMORY_LOAD_CONCURRENCY,
        help="Concurrency used for active memory load phase.",
    )
    parser.add_argument(
        "--skip-memory-load-test",
        action="store_true",
        help="Skip active load between memory snapshots.",
    )
    parser.add_argument("--restart-trials", type=int, default=3)
    parser.add_argument(
        "--ready-timeout-seconds", type=int, default=DEFAULT_READY_TIMEOUT_SECONDS
    )
    parser.add_argument(
        "--skip-rollback-drill",
        action="store_true",
        default=True,
        help="Deprecated flag retained for compatibility; rollback drill is always skipped.",
    )
    parser.add_argument(
        "--skip-restart-timing",
        action="store_true",
        help="Skip machine restart timing measurements.",
    )
    parser.add_argument(
        "--evidence-dir",
        default="",
        help="Optional evidence output directory. Default: .tmp/rehearsal_<timestamp>",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv()
    app_name = get_required_env("FLY_APP_NAME_DEV")
    date_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    evidence_dir = (
        Path(args.evidence_dir)
        if args.evidence_dir
        else Path(f".tmp/rehearsal_{date_tag}")
    )
    evidence_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Evidence dir: %s", evidence_dir)

    files: list[str] = []

    local_sha_result = run_command(["git", "rev-parse", "HEAD"], check=True)
    local_sha_path = evidence_dir / "local_sha.txt"
    local_sha_path.write_text(local_sha_result.stdout.strip() + "\n", encoding="utf-8")
    files.append(local_sha_path.name)

    run_command(
        [
            "poetry",
            "run",
            "python",
            "scripts/validate/validate_fly_release.py",
            "--env",
            args.env,
            "--expected-ref",
            "HEAD",
        ],
        output_path=evidence_dir / "release_validation.txt",
    )
    files.append("release_validation.txt")

    collect_latency_measurements(
        environment=args.env,
        game_id=args.game_id,
        samples=max(args.latency_samples, 1),
        output_path=evidence_dir / "latency_measurements.json",
    )
    files.append("latency_measurements.json")

    capture_memory_snapshot(
        app_name=app_name,
        output_path=evidence_dir / "memory_workers_snapshot_1.txt",
    )
    files.append("memory_workers_snapshot_1.txt")
    if args.skip_memory_load_test:
        logger.info("Skipping active memory load test by request.")
    else:
        run_memory_active_load(
            environment=args.env,
            game_id=args.game_id,
            requests_per_endpoint=max(args.memory_load_requests, 1),
            concurrency=max(args.memory_load_concurrency, 1),
            output_path=evidence_dir / "memory_active_load_summary.json",
        )
        files.append("memory_active_load_summary.json")
    if args.memory_interval_seconds > 0:
        logger.info(
            "Waiting %ss before second memory snapshot.", args.memory_interval_seconds
        )
        time.sleep(args.memory_interval_seconds)
    capture_memory_snapshot(
        app_name=app_name,
        output_path=evidence_dir / "memory_workers_snapshot_2.txt",
    )
    files.append("memory_workers_snapshot_2.txt")

    if not args.skip_restart_timing:
        measure_restart_timing(
            app_name=app_name,
            output_path=evidence_dir / "startup_restart_times.txt",
            trials=max(args.restart_trials, 1),
            ready_timeout_seconds=max(args.ready_timeout_seconds, 30),
        )
        files.append("startup_restart_times.txt")

    logger.info(
        "Rollback drill automation is disabled in this script. "
        "Run rollback drills manually via deploy runbook commands."
    )

    preconvention_commands = [
        (
            "preconvention_health.txt",
            [
                "poetry",
                "run",
                "python",
                "scripts/validate/validate_fly_health_checks.py",
                "--env",
                args.env,
            ],
        ),
        (
            "preconvention_auth.txt",
            [
                "poetry",
                "run",
                "python",
                "scripts/validate/validate_auth_flow.py",
                "--env",
                args.env,
            ],
        ),
        (
            "preconvention_recs.txt",
            [
                "poetry",
                "run",
                "python",
                "scripts/validate/validate_recommendation_endpoint.py",
                "--env",
                args.env,
                "--game-id",
                str(args.game_id),
            ],
        ),
        (
            "preconvention_perf_gate.txt",
            [
                "poetry",
                "run",
                "python",
                "scripts/validate/validate_performance_gate.py",
                "--env",
                args.env,
            ],
        ),
        (
            "preconvention_alert_path_static.txt",
            [
                "poetry",
                "run",
                "python",
                "scripts/validate/validate_prod_alert_path.py",
                "--env",
                "prod",
                "--skip-runtime",
            ],
        ),
    ]

    for filename, command in preconvention_commands:
        run_command(command, output_path=evidence_dir / filename)
        files.append(filename)

    write_summary(evidence_dir=evidence_dir, files=files)
    logger.info("Rehearsal evidence collection complete.")
    logger.info("Summary: %s", evidence_dir / "README.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
