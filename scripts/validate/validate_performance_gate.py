#!/usr/bin/env python3

import argparse
import logging
import sys

try:
    from validation_common import build_url, fetch_json, measure_json_request
except ModuleNotFoundError:
    from scripts.validation_common import build_url, fetch_json, measure_json_request


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def assert_duration(name: str, duration_ms: float, threshold_ms: int) -> None:
    logger.info("%s latency: %.1fms (threshold: %dms)", name, duration_ms, threshold_ms)
    if duration_ms > threshold_ms:
        raise RuntimeError(
            f"{name} exceeded latency threshold ({duration_ms:.1f}ms > {threshold_ms}ms)."
        )


def validate_performance_gate(
    environment: str,
    game_id: int,
    root_threshold_ms: int,
    version_threshold_ms: int,
    recommendation_threshold_ms: int,
) -> int:
    logger.info("Environment: %s", environment)

    # Warm the app once so the gate measures steady-state latency instead of cold starts.
    fetch_json(build_url(environment, "/api"))

    api_payload, api_duration = measure_json_request(build_url(environment, "/api"))
    version_payload, version_duration = measure_json_request(
        build_url(environment, "/api/version")
    )
    recommendations_payload, recommendation_duration = measure_json_request(
        build_url(
            environment,
            f"/api/recommendations/{game_id}",
            {"limit": 5},
        )
    )

    if api_payload.get("message") != "Board Game Recommender API":
        raise RuntimeError("Unexpected /api response payload during performance gate.")
    if version_payload.get("git_sha") in (None, "", "unknown"):
        raise RuntimeError("Unexpected /api/version payload during performance gate.")
    if not isinstance(recommendations_payload, list):
        raise RuntimeError(
            "Recommendation endpoint did not return a JSON list during performance gate."
        )

    assert_duration("/api", api_duration, root_threshold_ms)
    assert_duration("/api/version", version_duration, version_threshold_ms)
    assert_duration(
        f"/api/recommendations/{game_id}",
        recommendation_duration,
        recommendation_threshold_ms,
    )

    logger.info("Performance gate passed.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate basic response-time thresholds before promotion."
    )
    parser.add_argument(
        "--env",
        choices=["dev", "prod"],
        required=True,
        help="Target Fly environment to validate.",
    )
    parser.add_argument(
        "--game-id",
        type=int,
        default=224517,
        help="Known-good game ID expected to return recommendations.",
    )
    parser.add_argument(
        "--root-threshold-ms",
        type=int,
        default=1500,
        help="Maximum acceptable latency for /api.",
    )
    parser.add_argument(
        "--version-threshold-ms",
        type=int,
        default=1500,
        help="Maximum acceptable latency for /api/version.",
    )
    parser.add_argument(
        "--recommendation-threshold-ms",
        type=int,
        default=4000,
        help="Maximum acceptable latency for the recommendation endpoint.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return validate_performance_gate(
            args.env,
            args.game_id,
            args.root_threshold_ms,
            args.version_threshold_ms,
            args.recommendation_threshold_ms,
        )
    except Exception as exc:
        logger.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
