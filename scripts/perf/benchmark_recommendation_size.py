#!/usr/bin/env python3

import argparse
import json
import logging
import random
import statistics
import sys
import time
import urllib.error
import urllib.request
from collections import Counter

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

try:
    from validation_common import build_url
except ModuleNotFoundError:
    from scripts.validation_common import build_url


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@retry(
    retry=retry_if_exception_type((urllib.error.URLError, TimeoutError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.3, min=0.3, max=2),
)
def post_json_once(url: str, payload: dict, timeout: int = 90) -> tuple[int, float]:
    started = time.perf_counter()
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url=url,
        method="POST",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            _ = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        _ = exc.read()
        status = exc.code
    duration_ms = (time.perf_counter() - started) * 1000
    return status, duration_ms


def parse_csv_ints(raw: str) -> list[int]:
    values: list[int] = []
    for item in raw.split(","):
        stripped = item.strip()
        if not stripped:
            continue
        values.append(int(stripped))
    if not values:
        raise ValueError("Expected at least one integer value.")
    return values


def percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    idx = int(round((pct / 100.0) * (len(sorted_values) - 1)))
    return sorted_values[max(0, min(idx, len(sorted_values) - 1))]


def benchmark_size(
    environment: str,
    candidate_game_ids: list[int],
    liked_count: int,
    iterations: int,
    recommendation_limit: int,
    pax_only: bool,
) -> dict:
    url = build_url(environment, "/api/recommendations")
    latencies: list[float] = []
    statuses: Counter[int] = Counter()

    for _ in range(iterations):
        liked_games = random.sample(candidate_game_ids, k=liked_count)
        payload = {
            "liked_games": liked_games,
            "limit": recommendation_limit,
            "pax_only": pax_only,
        }
        status, duration_ms = post_json_once(url, payload)
        statuses[status] += 1
        latencies.append(duration_ms)

    latencies_sorted = sorted(latencies)
    success_count = statuses.get(200, 0)
    error_count = iterations - success_count

    return {
        "liked_count": liked_count,
        "iterations": iterations,
        "success_count": success_count,
        "error_count": error_count,
        "error_rate": (error_count / iterations) * 100.0,
        "p50_ms": percentile(latencies_sorted, 50),
        "p90_ms": percentile(latencies_sorted, 90),
        "p95_ms": percentile(latencies_sorted, 95),
        "max_ms": max(latencies_sorted) if latencies_sorted else 0.0,
        "avg_ms": statistics.fmean(latencies_sorted) if latencies_sorted else 0.0,
        "status_counts": dict(sorted(statuses.items())),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark /api/recommendations latency vs liked-games list size."
    )
    parser.add_argument(
        "--env",
        choices=["local", "dev", "prod"],
        required=True,
        help="Target environment.",
    )
    parser.add_argument(
        "--game-ids",
        required=True,
        help="CSV candidate game IDs used for random liked-game sampling.",
    )
    parser.add_argument(
        "--sizes",
        default="1,5,10,20,35,50",
        help="CSV list of liked-game counts to benchmark.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=20,
        help="Requests per liked-game size.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Recommendation result limit per request.",
    )
    parser.add_argument(
        "--pax-only",
        choices=["true", "false"],
        default="true",
        help="Whether to set pax_only in request payload.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        candidate_game_ids = list(dict.fromkeys(parse_csv_ints(args.game_ids)))
        sizes = parse_csv_ints(args.sizes)
    except ValueError as exc:
        logger.error("Invalid input: %s", exc)
        return 1

    if args.iterations < 1:
        logger.error("--iterations must be >= 1")
        return 1
    if args.limit < 1:
        logger.error("--limit must be >= 1")
        return 1

    max_size = max(sizes)
    if len(candidate_game_ids) < max_size:
        logger.error(
            "Need at least %d candidate IDs for requested sizes, but got %d.",
            max_size,
            len(candidate_game_ids),
        )
        return 1

    random.seed(42)
    pax_only = args.pax_only == "true"

    logger.info("Environment: %s", args.env)
    logger.info("Candidate IDs: %d", len(candidate_game_ids))
    logger.info("Sizes: %s", sizes)
    logger.info("Iterations per size: %d", args.iterations)
    logger.info("Payload pax_only: %s", pax_only)
    logger.info("Payload limit: %d", args.limit)

    summary_rows: list[dict] = []
    for liked_count in sizes:
        result = benchmark_size(
            environment=args.env,
            candidate_game_ids=candidate_game_ids,
            liked_count=liked_count,
            iterations=args.iterations,
            recommendation_limit=args.limit,
            pax_only=pax_only,
        )
        summary_rows.append(result)
        logger.info(
            "size=%d success=%d/%d error_rate=%.2f%% p50=%.1fms p95=%.1fms max=%.1fms statuses=%s",
            result["liked_count"],
            result["success_count"],
            result["iterations"],
            result["error_rate"],
            result["p50_ms"],
            result["p95_ms"],
            result["max_ms"],
            result["status_counts"],
        )

    print(json.dumps({"environment": args.env, "results": summary_rows}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
