#!/usr/bin/env python3

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import logging
import os
from pathlib import Path
import statistics
import time
import urllib.parse
import urllib.error
import urllib.request
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine

from scripts.validation_common import build_url, load_dotenv


logger = logging.getLogger(__name__)


DEFAULT_ENDPOINTS = [
    ("GET", "/api/games/?limit=24&skip=0&sort_by=rank"),
    ("GET", "/api/games/224517"),
    ("GET", "/api/recommendations/224517?limit=24"),
    ("GET", "/api/filter-options/"),
]

DEFAULT_ADMIN_ENDPOINTS = [
    ("GET", "/api/admin/users?limit=25&offset=0"),
    ("GET", "/api/admin/library-imports?limit=25&offset=0"),
]


@dataclass(frozen=True)
class EndpointCase:
    method: str
    path: str
    expected_status: int = 200


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def parse_endpoint(raw_endpoint: str) -> EndpointCase:
    if ":" in raw_endpoint:
        status_str, endpoint_text = raw_endpoint.split(":", 1)
        expected_status = int(status_str)
    else:
        endpoint_text = raw_endpoint
        expected_status = 200

    pieces = endpoint_text.strip().split(maxsplit=1)
    if len(pieces) != 2:
        raise ValueError(
            f"Invalid endpoint spec '{raw_endpoint}'. Expected 'METHOD /path' or 'STATUS:METHOD /path'."
        )
    method, path = pieces
    method = method.upper()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        raise ValueError(f"Unsupported method '{method}' in endpoint spec '{raw_endpoint}'.")
    if not path.startswith("/"):
        raise ValueError(f"Endpoint path must start with '/': '{raw_endpoint}'")
    return EndpointCase(method=method, path=path, expected_status=expected_status)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if pct <= 0:
        return min(values)
    if pct >= 1:
        return max(values)
    sorted_values = sorted(values)
    index = int((len(sorted_values) - 1) * pct)
    return sorted_values[index]


def normalize_sql(statement: str) -> str:
    compact = " ".join(statement.split())
    if len(compact) <= 240:
        return compact
    return compact[:237] + "..."


class SqlProfiler:
    # Local in-process SQL profiler (used only for --environment local).
    def __init__(self, db_engine: Engine):
        self._engine = db_engine
        self._active = False
        self._entries: list[dict[str, Any]] = []

    def _before_cursor_execute(
        self,
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ) -> None:
        conn.info.setdefault("_query_start_time", []).append(time.perf_counter())

    def _after_cursor_execute(
        self,
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ) -> None:
        starts = conn.info.get("_query_start_time", [])
        if not starts:
            return
        started = starts.pop(-1)
        if not self._active:
            return
        self._entries.append(
            {
                "sql": normalize_sql(statement),
                "duration_ms": (time.perf_counter() - started) * 1000,
            }
        )

    def __enter__(self) -> SqlProfiler:
        event.listen(self._engine, "before_cursor_execute", self._before_cursor_execute)
        event.listen(self._engine, "after_cursor_execute", self._after_cursor_execute)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        event.remove(self._engine, "before_cursor_execute", self._before_cursor_execute)
        event.remove(self._engine, "after_cursor_execute", self._after_cursor_execute)

    def start_request(self) -> None:
        self._entries = []
        self._active = True

    def end_request(self) -> list[dict[str, Any]]:
        self._active = False
        return list(self._entries)


def summarize_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    response_ms = [float(run["response_ms"]) for run in runs]
    sql_counts = [int(run["sql_count"]) for run in runs]
    sql_time_ms = [float(run["sql_time_ms"]) for run in runs]
    failures = [run for run in runs if not run["ok"]]
    return {
        "iterations": len(runs),
        "failures": len(failures),
        "response_ms": {
            "p50": round(statistics.median(response_ms), 2) if response_ms else 0.0,
            "p95": round(percentile(response_ms, 0.95), 2),
            "max": round(max(response_ms), 2) if response_ms else 0.0,
        },
        "sql_count": {
            "avg": round(statistics.mean(sql_counts), 2) if sql_counts else 0.0,
            "p95": round(percentile([float(v) for v in sql_counts], 0.95), 2),
            "max": max(sql_counts) if sql_counts else 0,
        },
        "sql_time_ms": {
            "avg": round(statistics.mean(sql_time_ms), 2) if sql_time_ms else 0.0,
            "p95": round(percentile(sql_time_ms, 0.95), 2),
            "max": round(max(sql_time_ms), 2) if sql_time_ms else 0.0,
        },
    }


def summarize_top_sql(runs: list[dict[str, Any]], top_n: int) -> list[dict[str, Any]]:
    aggregate: dict[str, dict[str, Any]] = {}
    for run in runs:
        for item in run["sql_entries"]:
            sql = str(item["sql"])
            entry = aggregate.setdefault(sql, {"sql": sql, "count": 0, "total_ms": 0.0})
            entry["count"] += 1
            entry["total_ms"] += float(item["duration_ms"])
    ordered = sorted(aggregate.values(), key=lambda row: row["total_ms"], reverse=True)
    return [
        {
            "sql": row["sql"],
            "count": row["count"],
            "total_ms": round(float(row["total_ms"]), 2),
        }
        for row in ordered[:top_n]
    ]


def get_bearer_token_local(
    client: TestClient,
    *,
    username: str | None,
    password: str | None,
) -> str | None:
    if not username or not password:
        return None
    response = client.post(
        "/api/token",
        data={"username": username, "password": password},
    )
    if response.status_code != 200:
        logger.warning(
            "Admin auth failed for profile script (status=%s). Skipping admin endpoints.",
            response.status_code,
        )
        return None
    payload = response.json()
    token = payload.get("access_token")
    if not token:
        logger.warning("Auth response did not contain access_token. Skipping admin endpoints.")
        return None
    return str(token)


def get_bearer_token_remote(
    environment: str,
    *,
    username: str | None,
    password: str | None,
) -> str | None:
    if not username or not password:
        return None
    token_url = build_url(environment, "/api/token")
    payload = urllib.parse.urlencode(
        {"username": username, "password": password}
    ).encode("utf-8")
    request = urllib.request.Request(
        token_url,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=payload,
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
    except Exception as exc:  # pragma: no cover - network behavior
        logger.warning(
            "Admin auth failed for remote profile script (%s). Skipping admin endpoints.",
            exc,
        )
        return None
    try:
        token = json.loads(body).get("access_token")
    except json.JSONDecodeError:  # pragma: no cover - defensive
        logger.warning("Remote auth response was not JSON. Skipping admin endpoints.")
        return None
    if not token:
        logger.warning("Remote auth response did not contain access_token.")
        return None
    return str(token)


def run_profile_local(
    endpoints: list[EndpointCase],
    *,
    iterations: int,
    admin_username: str | None,
    admin_password: str | None,
    top_sql: int,
) -> dict[str, Any]:
    from fastapi.testclient import TestClient

    from backend.app.database import engine
    from backend.app.main import app

    generated_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    report: dict[str, Any] = {
        "generated_at": generated_at,
        "iterations": iterations,
        "environment": "local",
        "sql_metrics_available": True,
        "results": [],
    }

    with TestClient(app) as client, SqlProfiler(engine) as profiler:
        token = get_bearer_token_local(
            client,
            username=admin_username,
            password=admin_password,
        )
        for endpoint in endpoints:
            logger.info(
                "Profiling %s %s (%s iterations)",
                endpoint.method,
                endpoint.path,
                iterations,
            )
            endpoint_runs: list[dict[str, Any]] = []
            for _ in range(iterations):
                headers = {}
                if endpoint.path.startswith("/api/admin/"):
                    if not token:
                        endpoint_runs.append(
                            {
                                "ok": False,
                                "status_code": 0,
                                "response_ms": 0.0,
                                "sql_count": 0,
                                "sql_time_ms": 0.0,
                                "sql_entries": [],
                                "error": "missing_admin_token",
                            }
                        )
                        continue
                    headers["Authorization"] = f"Bearer {token}"

                profiler.start_request()
                started = time.perf_counter()
                response = client.request(endpoint.method, endpoint.path, headers=headers)
                response_ms = (time.perf_counter() - started) * 1000
                sql_entries = profiler.end_request()
                sql_time_ms = sum(float(item["duration_ms"]) for item in sql_entries)
                ok = response.status_code == endpoint.expected_status
                endpoint_runs.append(
                    {
                        "ok": ok,
                        "status_code": response.status_code,
                        "response_ms": round(response_ms, 2),
                        "sql_count": len(sql_entries),
                        "sql_time_ms": round(sql_time_ms, 2),
                        "sql_entries": sql_entries,
                    }
                )

            report["results"].append(
                {
                    "endpoint": f"{endpoint.method} {endpoint.path}",
                    "expected_status": endpoint.expected_status,
                    "summary": summarize_runs(endpoint_runs),
                    "top_sql": summarize_top_sql(endpoint_runs, top_sql),
                }
            )

    return report


def run_profile_remote(
    endpoints: list[EndpointCase],
    *,
    iterations: int,
    environment: str,
    admin_username: str | None,
    admin_password: str | None,
    top_sql: int,
) -> dict[str, Any]:
    generated_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    report: dict[str, Any] = {
        "generated_at": generated_at,
        "iterations": iterations,
        "environment": environment,
        "sql_metrics_available": False,
        "results": [],
    }

    token = get_bearer_token_remote(
        environment,
        username=admin_username,
        password=admin_password,
    )
    for endpoint in endpoints:
        logger.info(
            "Profiling %s %s on %s (%s iterations)",
            endpoint.method,
            endpoint.path,
            environment,
            iterations,
        )
        endpoint_runs: list[dict[str, Any]] = []
        for _ in range(iterations):
            if endpoint.path.startswith("/api/admin/") and not token:
                endpoint_runs.append(
                    {
                        "ok": False,
                        "status_code": 0,
                        "response_ms": 0.0,
                        "sql_count": 0,
                        "sql_time_ms": 0.0,
                        "sql_entries": [],
                        "error": "missing_admin_token",
                    }
                )
                continue

            url = build_url(environment, endpoint.path)
            headers = {"Accept": "application/json"}
            if endpoint.path.startswith("/api/admin/") and token:
                headers["Authorization"] = f"Bearer {token}"
            request = urllib.request.Request(url=url, method=endpoint.method, headers=headers)

            status_code = 0
            ok = False
            started = time.perf_counter()
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    response.read()
                    status_code = int(response.status)
            except urllib.error.HTTPError as exc:
                status_code = int(exc.code)
            except Exception:  # pragma: no cover - network behavior
                status_code = 0
            response_ms = (time.perf_counter() - started) * 1000
            ok = status_code == endpoint.expected_status
            endpoint_runs.append(
                {
                    "ok": ok,
                    "status_code": status_code,
                    "response_ms": round(response_ms, 2),
                    "sql_count": 0,
                    "sql_time_ms": 0.0,
                    "sql_entries": [],
                }
            )

        report["results"].append(
            {
                "endpoint": f"{endpoint.method} {endpoint.path}",
                "expected_status": endpoint.expected_status,
                "summary": summarize_runs(endpoint_runs),
                "top_sql": summarize_top_sql(endpoint_runs, top_sql),
            }
        )
    return report


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Profile hot backend endpoints for response latency and SQL query behavior."
    )
    parser.add_argument(
        "--environment",
        choices=["local", "dev", "prod"],
        default="local",
        help="Target environment. local=TestClient+SQL metrics, dev/prod=live HTTP on Fly.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
        help="Number of requests per endpoint (default: 10).",
    )
    parser.add_argument(
        "--endpoint",
        action="append",
        default=[],
        help="Endpoint spec: 'METHOD /path' or 'STATUS:METHOD /path'. Can be repeated.",
    )
    parser.add_argument(
        "--include-admin",
        action="store_true",
        help="Include default admin endpoints (requires admin credentials).",
    )
    parser.add_argument(
        "--admin-username",
        default=os.getenv("SMOKE_TEST_USERNAME"),
        help="Admin username for admin endpoint profiling (default: SMOKE_TEST_USERNAME).",
    )
    parser.add_argument(
        "--admin-password",
        default=(
            os.getenv("SMOKE_TEST_PASSWORD_DEV")
            or os.getenv("SMOKE_TEST_PASSWORD")
            or os.getenv("ADMIN_PASSWORD")
        ),
        help="Admin password for admin endpoint profiling.",
    )
    parser.add_argument(
        "--top-sql",
        type=int,
        default=10,
        help="Number of top SQL statements to include per endpoint (default: 10).",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional explicit output file path. Default writes to logs/profiling/backend_queries/",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    args = parser.parse_args()

    configure_logging(args.verbose)

    if args.iterations <= 0:
        raise ValueError("--iterations must be > 0.")
    if args.top_sql <= 0:
        raise ValueError("--top-sql must be > 0.")

    endpoint_specs = args.endpoint or [f"{m} {p}" for m, p in DEFAULT_ENDPOINTS]
    if args.include_admin:
        endpoint_specs.extend(f"{m} {p}" for m, p in DEFAULT_ADMIN_ENDPOINTS)
    endpoints = [parse_endpoint(spec) for spec in endpoint_specs]

    if args.environment == "local":
        report = run_profile_local(
            endpoints,
            iterations=args.iterations,
            admin_username=args.admin_username,
            admin_password=args.admin_password,
            top_sql=args.top_sql,
        )
    else:
        report = run_profile_remote(
            endpoints,
            iterations=args.iterations,
            environment=args.environment,
            admin_username=args.admin_username,
            admin_password=args.admin_password,
            top_sql=args.top_sql,
        )

    output_path: Path
    if args.output:
        output_path = Path(args.output)
    else:
        out_dir = Path("logs/profiling/backend_queries")
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        output_path = out_dir / f"hot_endpoints.{stamp}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Wrote profiling report: %s", output_path)
    print(str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
