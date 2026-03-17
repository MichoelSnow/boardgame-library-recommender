#!/usr/bin/env python3

import argparse
import logging
import subprocess
import sys


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

VALIDATED_SHA_PATH = ".tmp/validated_dev_sha.txt"
POETRY_PYTHON = ["poetry", "run", "python"]

DEFAULT_GAME_ID = "224517"


def detect_expected_ref() -> str:
    branch_result = subprocess.run(
        ["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
        capture_output=True,
        text=True,
    )
    if branch_result.returncode == 0:
        branch_name = branch_result.stdout.strip()
        if branch_name:
            return branch_name
    return "HEAD"


def build_validation_steps(
    environment: str, expected_ref: str
) -> list[tuple[str, list[str]]]:
    return [
        (
            "Release metadata and SHA",
            [
                *POETRY_PYTHON,
                "scripts/validate/validate_fly_release.py",
                "--env",
                environment,
                "--expected-ref",
                expected_ref,
                "--write-sha-path",
                VALIDATED_SHA_PATH,
            ],
        ),
        (
            "Fly health checks",
            [
                *POETRY_PYTHON,
                "scripts/validate/validate_fly_health_checks.py",
                "--env",
                environment,
            ],
        ),
        (
            "Auth flow smoke test",
            [
                *POETRY_PYTHON,
                "scripts/validate/validate_auth_flow.py",
                "--env",
                environment,
            ],
        ),
        (
            "Recommendation artifact files",
            [
                *POETRY_PYTHON,
                "scripts/validate/validate_recommendation_artifacts.py",
                "--env",
                environment,
            ],
        ),
        (
            "Recommendation endpoint smoke test",
            [
                *POETRY_PYTHON,
                "scripts/validate/validate_recommendation_endpoint.py",
                "--env",
                environment,
                "--game-id",
                DEFAULT_GAME_ID,
            ],
        ),
        (
            "Performance gate",
            [
                *POETRY_PYTHON,
                "scripts/validate/validate_performance_gate.py",
                "--env",
                environment,
                "--game-id",
                DEFAULT_GAME_ID,
            ],
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run core dev deployment validation checks."
    )
    parser.add_argument(
        "--env",
        choices=["dev", "prod"],
        default="dev",
        help="Target Fly environment to validate (default: dev).",
    )
    parser.add_argument(
        "--expected-ref",
        default="",
        help="Git ref to validate deployed SHA against. Defaults to current branch, or HEAD in detached mode.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    expected_ref = args.expected_ref or detect_expected_ref()
    logger.info("Using expected git ref: %s", expected_ref)

    for name, command in build_validation_steps(args.env, expected_ref):
        exit_code = run_step(name, command)
        if exit_code != 0:
            return exit_code

    logger.info("Core dev deployment validation passed.")
    logger.info("Validated dev SHA recorded at %s", VALIDATED_SHA_PATH)
    logger.info(
        "If the merge changed frontend behavior, auth flows, or deployment config, "
        "run the additional manual checks listed in docs/core/runbook.md."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
