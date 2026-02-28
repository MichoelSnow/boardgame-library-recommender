#!/usr/bin/env python3

import logging
import subprocess
import sys


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

VALIDATED_SHA_PATH = ".tmp/validated_dev_sha.txt"

VALIDATION_STEPS = [
    (
        "Release metadata and SHA",
        [
            "python",
            "scripts/validate_fly_release.py",
            "--env",
            "dev",
            "--expected-ref",
            "main",
            "--write-sha-path",
            VALIDATED_SHA_PATH,
        ],
    ),
    (
        "Fly health checks",
        ["python", "scripts/validate_fly_health_checks.py", "--env", "dev"],
    ),
    (
        "Auth flow smoke test",
        ["python", "scripts/validate_auth_flow.py", "--env", "dev"],
    ),
    (
        "Recommendation artifact files",
        ["python", "scripts/validate_recommendation_artifacts.py", "--env", "dev"],
    ),
    (
        "Recommendation endpoint smoke test",
        ["python", "scripts/validate_recommendation_endpoint.py", "--env", "dev", "--game-id", "224517"],
    ),
    (
        "Performance gate",
        ["python", "scripts/validate_performance_gate.py", "--env", "dev", "--game-id", "224517"],
    ),
]


def run_step(name: str, command: list[str]) -> int:
    logger.info("Running: %s", name)
    result = subprocess.run(command)
    if result.returncode != 0:
        logger.error("Failed: %s", name)
        return result.returncode
    logger.info("Passed: %s", name)
    return 0


def main() -> int:
    for name, command in VALIDATION_STEPS:
        exit_code = run_step(name, command)
        if exit_code != 0:
            return exit_code

    logger.info("Core dev deployment validation passed.")
    logger.info("Validated dev SHA recorded at %s", VALIDATED_SHA_PATH)
    logger.info(
        "If the merge changed frontend behavior, auth flows, or deployment config, "
        "run the additional manual checks listed in docs/deploy_rollback_runbook.md."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
