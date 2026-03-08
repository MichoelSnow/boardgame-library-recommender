#!/usr/bin/env python3

import argparse
import logging
import re
import subprocess
import sys

try:
    from validation_common import get_app_name, run_command
except ModuleNotFoundError:
    from scripts.validation_common import get_app_name, run_command


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

RELEASE_LINE_PATTERN = re.compile(r"^\s*(v\d+)\s+(\w+)")


def parse_releases(stdout: str) -> list[tuple[str, str]]:
    releases: list[tuple[str, str]] = []
    for line in stdout.splitlines():
        match = RELEASE_LINE_PATTERN.match(line)
        if not match:
            continue
        releases.append((match.group(1), match.group(2).lower()))
    return releases


def resolve_rollback_target(
    releases: list[tuple[str, str]],
    target_release: str | None,
) -> tuple[str, str]:
    if not releases:
        raise RuntimeError("No Fly releases were found.")

    current_release = releases[0][0]

    if target_release:
        for release_version, status in releases:
            if release_version == target_release:
                if status != "complete":
                    raise RuntimeError(
                        f"Requested rollback target {target_release} is not complete."
                    )
                return current_release, target_release
        raise RuntimeError(f"Requested rollback target {target_release} was not found.")

    for release_version, status in releases[1:]:
        if status == "complete":
            return current_release, release_version

    raise RuntimeError("No previous complete Fly release is available for rollback.")


def prepare_rollback(environment: str, target_release: str | None) -> int:
    app_name = get_app_name(environment)
    try:
        result = run_command(["fly", "releases", "-a", app_name])
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise RuntimeError(
            f"Failed to query Fly releases for {app_name}: {stderr or exc}"
        ) from exc

    releases = parse_releases(result.stdout)
    current_release, resolved_target = resolve_rollback_target(releases, target_release)

    logger.info("Environment: %s", environment)
    logger.info("Current Fly release: %s", current_release)
    logger.info("Rollback target: %s", resolved_target)
    logger.info(
        "Rollback command: fly releases rollback %s -a %s",
        resolved_target,
        app_name,
    )
    logger.info("Rollback path validation passed.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve and print the safe Fly rollback command."
    )
    parser.add_argument(
        "--env",
        choices=["dev", "prod"],
        required=True,
        help="Target Fly environment to inspect.",
    )
    parser.add_argument(
        "--target-release",
        help="Optional explicit Fly release version to use as the rollback target.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return prepare_rollback(args.env, args.target_release)
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
