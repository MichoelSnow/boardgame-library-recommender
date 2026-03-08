#!/usr/bin/env python3

import argparse
import logging
import subprocess
import sys

try:
    from validation_common import get_app_name, run_command
except ModuleNotFoundError:
    from scripts.validation_common import get_app_name, run_command


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def normalize_check_lines(stdout: str) -> list[str]:
    lines = []
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("Health Checks for "):
            continue
        if stripped.startswith("App "):
            continue
        if stripped.startswith("NAME "):
            continue
        if all(char in "-*| " for char in stripped):
            continue
        lines.append(stripped)
    return lines


def validate_health_checks(environment: str) -> int:
    app_name = get_app_name(environment)
    try:
        result = run_command(["fly", "checks", "list", "-a", app_name])
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise RuntimeError(
            f"Failed to query Fly health checks for {app_name}: {stderr or exc}"
        ) from exc

    lines = normalize_check_lines(result.stdout)
    joined_output = "\n".join(lines).lower()

    logger.info("Environment: %s", environment)
    if not lines or "no health checks" in joined_output:
        logger.error("No Fly health checks are configured for %s.", app_name)
        return 1

    if "passing" not in joined_output:
        logger.error("No passing Fly health checks found for %s.", app_name)
        return 1

    for unhealthy_marker in ("critical", "failing", "warning"):
        if unhealthy_marker in joined_output:
            logger.error(
                "Detected non-passing Fly health check status (%s) for %s.",
                unhealthy_marker,
                app_name,
            )
            return 1

    logger.info("Fly health checks are configured and passing for %s.", app_name)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate Fly health checks for a target environment."
    )
    parser.add_argument(
        "--env",
        choices=["dev", "prod"],
        required=True,
        help="Target Fly environment to validate.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return validate_health_checks(args.env)
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
