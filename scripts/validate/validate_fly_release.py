#!/usr/bin/env python3

import argparse
import logging
from pathlib import Path
import sys

try:
    from validation_common import fetch_json, get_base_url, run_command
except ModuleNotFoundError:
    from scripts.validation_common import fetch_json, get_base_url, run_command


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def run_git_rev_parse(git_ref: str) -> str:
    try:
        return run_command(["git", "rev-parse", git_ref]).stdout.strip()
    except Exception as exc:
        raise RuntimeError(f"Failed to resolve git ref '{git_ref}'.") from exc


def validate_release(
    environment: str,
    expected_ref: str,
    write_sha_path: str | None = None,
) -> int:
    base_url = get_base_url(environment)
    expected_sha = run_git_rev_parse(expected_ref)
    try:
        api_payload, _ = fetch_json(f"{base_url}/api")
        version_payload, _ = fetch_json(f"{base_url}/api/version")
    except Exception as exc:
        raise RuntimeError(f"Release validation request failed: {exc}") from exc

    if api_payload.get("message") != "Board Game Recommender API":
        logger.error("Unexpected /api payload: %s", api_payload)
        return 1

    deployed_sha = version_payload.get("git_sha")
    build_timestamp = version_payload.get("build_timestamp")

    logger.info("Environment: %s", environment)
    logger.info("Expected SHA (%s): %s", expected_ref, expected_sha)
    logger.info("Deployed SHA: %s", deployed_sha)
    logger.info("Build timestamp: %s", build_timestamp)

    if deployed_sha != expected_sha:
        logger.error("SHA mismatch between %s and deployed app.", expected_ref)
        return 1

    if not build_timestamp or build_timestamp == "unknown":
        logger.error("Build timestamp is missing or unknown.")
        return 1

    if write_sha_path:
        output_path = Path(write_sha_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"{deployed_sha}\n")
        logger.info("Wrote validated SHA to: %s", output_path)

    logger.info("Release validation passed.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate Fly app liveness and deployed git SHA."
    )
    parser.add_argument(
        "--env",
        choices=["dev", "prod"],
        required=True,
        help="Target Fly environment to validate.",
    )
    parser.add_argument(
        "--expected-ref",
        default="main",
        help="Git ref that the deployed app should match (default: main).",
    )
    parser.add_argument(
        "--write-sha-path",
        help="Optional file path to write the validated deployed SHA on success.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return validate_release(args.env, args.expected_ref, args.write_sha_path)
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
