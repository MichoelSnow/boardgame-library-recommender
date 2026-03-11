#!/usr/bin/env python3

import argparse
import logging
import sys

try:
    from validation_common import build_url, request_with_retry
except ModuleNotFoundError:
    from scripts.validation_common import build_url, request_with_retry


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def fetch_recommendations(
    environment: str, game_id: int, limit: int
) -> tuple[list, dict[str, str]]:
    url = build_url(
        environment,
        f"/api/recommendations/{game_id}",
        {"limit": limit},
    )
    try:
        payload, response_headers = request_with_retry(url)
    except Exception as exc:
        raise RuntimeError(
            f"Recommendation endpoint failed for {environment}: {exc}"
        ) from exc

    if not isinstance(payload, list):
        raise RuntimeError("Recommendation endpoint did not return a JSON list.")

    return payload, response_headers


def validate_recommendations(environment: str, game_id: int, limit: int) -> int:
    payload, response_headers = fetch_recommendations(environment, game_id, limit)

    logger.info("Environment: %s", environment)
    logger.info("Game ID: %s", game_id)
    logger.info("Recommendations returned: %d", len(payload))

    if response_headers.get("X-Recommendations-Available", "").lower() == "false":
        logger.error(
            "Recommendation endpoint reported degraded mode via response headers."
        )
        return 1

    if not payload:
        logger.error(
            "Recommendation endpoint returned an empty list. "
            "This may indicate degraded mode or unhealthy artifacts."
        )
        return 1

    sample_ids = [item.get("id") for item in payload[: min(3, len(payload))]]
    logger.info("Sample recommendation IDs: %s", sample_ids)
    logger.info("Recommendation endpoint validation passed.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate Fly recommendation endpoint against a known-good game ID."
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
        "--limit",
        type=int,
        default=5,
        help="Maximum number of recommendations to request.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return validate_recommendations(args.env, args.game_id, args.limit)
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
