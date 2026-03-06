#!/usr/bin/env python3

import logging
from pathlib import Path
import subprocess
import sys


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

VALIDATED_SHA_PATH = Path(".tmp/validated_dev_sha.txt")
POETRY_PYTHON = ["poetry", "run", "python"]


def read_validated_sha() -> str:
    if not VALIDATED_SHA_PATH.exists():
        raise RuntimeError(
            f"Validated SHA file not found at {VALIDATED_SHA_PATH}. "
            "Run poetry run python scripts/validate_dev_deploy.py first."
        )

    validated_sha = VALIDATED_SHA_PATH.read_text().strip()
    if not validated_sha:
        raise RuntimeError(
            f"Validated SHA file at {VALIDATED_SHA_PATH} is empty. "
            "Re-run poetry run python scripts/validate_dev_deploy.py."
        )
    return validated_sha


def run_step(name: str, command: list[str]) -> int:
    logger.info("Running: %s", name)
    result = subprocess.run(command)
    if result.returncode != 0:
        logger.error("Failed: %s", name)
        return result.returncode
    logger.info("Passed: %s", name)
    return 0


def main() -> int:
    try:
        validated_sha = read_validated_sha()
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1

    validation_steps = [
        (
            "Release metadata and SHA",
            [
                *POETRY_PYTHON,
                "scripts/validate_fly_release.py",
                "--env",
                "prod",
                "--expected-ref",
                validated_sha,
            ],
        ),
        (
            "Fly health checks",
            [*POETRY_PYTHON, "scripts/validate_fly_health_checks.py", "--env", "prod"],
        ),
        (
            "Auth flow smoke test",
            [*POETRY_PYTHON, "scripts/validate_auth_flow.py", "--env", "prod"],
        ),
        (
            "Recommendation artifact files",
            [*POETRY_PYTHON, "scripts/validate_recommendation_artifacts.py", "--env", "prod"],
        ),
        (
            "Recommendation endpoint smoke test",
            [
                *POETRY_PYTHON,
                "scripts/validate_recommendation_endpoint.py",
                "--env",
                "prod",
                "--game-id",
                "224517",
            ],
        ),
        (
            "Performance gate",
            [
                *POETRY_PYTHON,
                "scripts/validate_performance_gate.py",
                "--env",
                "prod",
                "--game-id",
                "224517",
            ],
        ),
        (
            "Record deploy traceability",
            [
                *POETRY_PYTHON,
                "scripts/record_deploy_traceability.py",
                "--env",
                "prod",
                "--expected-sha-path",
                str(VALIDATED_SHA_PATH),
                "--marker",
                "prod-promotion",
            ],
        ),
        (
            "Rollback path validation",
            [*POETRY_PYTHON, "scripts/prepare_fly_rollback.py", "--env", "prod"],
        ),
    ]

    logger.info("Using validated dev SHA: %s", validated_sha)
    for name, command in validation_steps:
        exit_code = run_step(name, command)
        if exit_code != 0:
            return exit_code

    logger.info("Core production release validation passed.")
    logger.info(
        "If the release changed frontend behavior, auth flows, or deployment config, "
        "run the additional manual checks listed in docs/runbooks/deploy_rollback_runbook.md."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
