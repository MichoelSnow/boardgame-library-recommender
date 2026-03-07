#!/usr/bin/env python3

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import subprocess
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

WORKFLOW_PATH = Path(".github/workflows/prod-health-alerts.yml")
ALERT_SCRIPT_PATH = Path("scripts/run_prod_health_alerts.py")
EXPECTED_CRON = 'cron: "*/20 * * * *"'
EXPECTED_RUN_COMMAND = "python scripts/run_prod_health_alerts.py --env prod"


def validate_static_configuration() -> None:
    if not WORKFLOW_PATH.exists():
        raise RuntimeError(f"Workflow file not found: {WORKFLOW_PATH}")
    if not ALERT_SCRIPT_PATH.exists():
        raise RuntimeError(f"Alert script not found: {ALERT_SCRIPT_PATH}")

    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
    if EXPECTED_CRON not in workflow_text:
        raise RuntimeError(
            f"Expected schedule '{EXPECTED_CRON}' not found in {WORKFLOW_PATH}."
        )
    if EXPECTED_RUN_COMMAND not in workflow_text:
        raise RuntimeError(
            f"Expected run command '{EXPECTED_RUN_COMMAND}' not found in {WORKFLOW_PATH}."
        )

    alert_script_text = ALERT_SCRIPT_PATH.read_text(encoding="utf-8")
    if "convention_mode_active" not in alert_script_text:
        raise RuntimeError(
            "Convention mode gate not found in alert script."
        )

    logger.info("Static alert-path configuration checks passed.")


def validate_runtime_dry_run(environment: str) -> None:
    logger.info("Running alert script dry-run for environment: %s", environment)
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_prod_health_alerts.py",
            "--env",
            environment,
            "--dry-run",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    # Dry-run can return 0 (convention mode off/healthy) or 1 (alert condition detected).
    if result.returncode not in {0, 1}:
        raise RuntimeError(
            "Dry-run execution failed unexpectedly with exit code "
            f"{result.returncode}. stderr={result.stderr.strip()}"
        )

    logger.info("Dry-run completed with exit code %s.", result.returncode)
    if result.stdout.strip():
        logger.info("Dry-run stdout: %s", result.stdout.strip())
    if result.stderr.strip():
        logger.info("Dry-run stderr: %s", result.stderr.strip())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate production alerting path configuration and dry-run behavior."
    )
    parser.add_argument(
        "--env",
        choices=["prod"],
        default="prod",
        help="Target environment for dry-run execution.",
    )
    parser.add_argument(
        "--skip-runtime",
        action="store_true",
        help="Skip dry-run execution and only validate static configuration.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        validate_static_configuration()
        if not args.skip_runtime:
            validate_runtime_dry_run(args.env)
        logger.info("Production alert path validation passed.")
        return 0
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
