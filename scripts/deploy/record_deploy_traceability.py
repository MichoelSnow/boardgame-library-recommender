#!/usr/bin/env python3

import argparse
import json
import logging
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from validation_common import fetch_json, get_app_name, get_base_url, run_command
except ModuleNotFoundError:
    from scripts.validation_common import (
        fetch_json,
        get_app_name,
        get_base_url,
        run_command,
    )


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

TRACEABILITY_LOG_PATH = Path("logs/deploy_traceability.jsonl")
RELEASE_VERSION_PATTERN = re.compile(r"^\s*(v\d+)\s+")


def get_latest_fly_release_version(app_name: str) -> str:
    try:
        result = run_command(["fly", "releases", "-a", app_name])
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise RuntimeError(
            f"Failed to query Fly releases for {app_name}: {stderr or exc}"
        ) from exc

    for line in result.stdout.splitlines():
        match = RELEASE_VERSION_PATTERN.match(line)
        if match:
            return match.group(1)

    raise RuntimeError(f"Could not determine latest Fly release version for {app_name}.")


def read_expected_sha(path_str: str | None) -> str | None:
    if not path_str:
        return None

    path = Path(path_str)
    if not path.exists():
        raise RuntimeError(f"Expected SHA file not found at {path}.")

    expected_sha = path.read_text().strip()
    if not expected_sha:
        raise RuntimeError(f"Expected SHA file at {path} is empty.")
    return expected_sha


def record_traceability(
    environment: str,
    marker: str | None,
    expected_sha_path: str | None,
) -> int:
    app_name = get_app_name(environment)
    base_url = get_base_url(environment)
    expected_sha = read_expected_sha(expected_sha_path)

    try:
        version_payload, _ = fetch_json(f"{base_url}/api/version")
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch /api/version for {environment}: {exc}") from exc

    deployed_sha = version_payload.get("git_sha")
    if expected_sha and deployed_sha != expected_sha:
        raise RuntimeError(
            f"Deployed SHA {deployed_sha} does not match expected SHA {expected_sha}."
        )

    release_version = get_latest_fly_release_version(app_name)
    record = {
        "recorded_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "environment": environment,
        "app_name": app_name,
        "base_url": base_url,
        "app_version": version_payload.get("app_version"),
        "git_sha": deployed_sha,
        "build_timestamp": version_payload.get("build_timestamp"),
        "fly_release_version": release_version,
        "marker": marker or "",
        "expected_sha": expected_sha,
    }

    TRACEABILITY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TRACEABILITY_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")

    logger.info("Recorded deploy traceability to %s", TRACEABILITY_LOG_PATH)
    logger.info("Environment: %s", environment)
    logger.info("Fly release version: %s", release_version)
    logger.info("Git SHA: %s", deployed_sha)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record deploy traceability for a Fly promotion."
    )
    parser.add_argument(
        "--env",
        choices=["dev", "prod"],
        required=True,
        help="Target Fly environment to record.",
    )
    parser.add_argument(
        "--marker",
        help="Optional release marker or note for this promotion event.",
    )
    parser.add_argument(
        "--expected-sha-path",
        help="Optional file containing the expected deployed SHA to verify.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return record_traceability(args.env, args.marker, args.expected_sha_path)
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
