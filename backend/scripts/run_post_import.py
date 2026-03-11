#!/usr/bin/env python
"""
Run Post-Import SQL Scripts

This script runs all SQL scripts in the scripts/sql directory.
It's designed to be run after data import or independently to update calculated fields.
"""

import sys
import argparse
import logging
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.append(str(backend_dir))

# Import SQL runner
from sql_runner import run_all_scripts, run_specific_scripts  # noqa: E402
from app.logging_utils import build_log_handlers  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=build_log_handlers("post_import.log"),
)
logger = logging.getLogger(__name__)


def main():
    """Run post-import SQL scripts."""
    parser = argparse.ArgumentParser(
        description="Run post-import SQL scripts for the Board Game Recommender"
    )
    parser.add_argument(
        "--script", help="Run a specific SQL script (without .sql extension)"
    )
    parser.add_argument(
        "--list", action="store_true", help="List available SQL scripts"
    )

    args = parser.parse_args()

    # Path to SQL scripts directory
    sql_dir = Path(__file__).parent / "sql"

    if args.list:
        # List available SQL scripts
        sql_files = sorted([f.name for f in sql_dir.glob("*.sql")])
        if not sql_files:
            logger.info("No SQL scripts found.")
            return

        logger.info("Available SQL scripts:")
        for i, script in enumerate(sql_files, 1):
            logger.info("%d. %s", i, script)
        return

    if args.script:
        # Run a specific SQL script
        logger.info(f"Running SQL script: {args.script}")
        try:
            run_specific_scripts([args.script])
            logger.info(f"Successfully ran SQL script: {args.script}")
        except Exception as e:
            logger.error(f"Error running SQL script: {str(e)}")
            sys.exit(1)
    else:
        # Run all SQL scripts
        logger.info("Running all post-import SQL scripts")
        try:
            run_all_scripts()
            logger.info("All post-import SQL scripts completed successfully")
        except Exception as e:
            logger.error(f"Error running SQL scripts: {str(e)}")
            sys.exit(1)


if __name__ == "__main__":
    main()
