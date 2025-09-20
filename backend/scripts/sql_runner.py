#!/usr/bin/env python
"""
SQL Script Runner for Board Game Recommender

This utility runs SQL scripts stored in the scripts/sql directory.
It can be used both as a standalone script and imported by other modules.
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from sqlalchemy import text, create_engine
from typing import List, Optional, Union

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.append(str(backend_dir))

from app.database import engine as app_engine

# Configure logging
log_dir = backend_dir / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
log_file_path = log_dir / "sql_runner.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(str(log_file_path)),
        logging.StreamHandler()
    ],
)
logger = logging.getLogger(__name__)

# Path to SQL scripts directory
SQL_SCRIPTS_DIR = Path(__file__).parent / "sql"

# Simple splitter: remove single-line comments and split on semicolons
# Good enough for our scripts; avoids SQLite's single-statement restriction

def _split_statements(sql: str) -> List[str]:
    lines: List[str] = []
    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('--'):
            continue
        lines.append(line)
    joined = "\n".join(lines)
    statements: List[str] = []
    current: List[str] = []
    for ch in joined:
        current.append(ch)
        if ch == ';':
            stmt = "".join(current).strip().rstrip(';').strip()
            if stmt:
                statements.append(stmt)
            current = []
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def run_sql_script(script_path: Union[str, Path], engine=None) -> None:
    """
    Run a single SQL script.
    
    Args:
        script_path: Path to the SQL script file
        engine: SQLAlchemy engine to use (defaults to app engine)
    """
    if engine is None:
        engine = app_engine
    
    script_path = Path(script_path)
    if not script_path.exists():
        raise FileNotFoundError(f"SQL script not found: {script_path}")
    
    logger.info(f"Running SQL script: {script_path.name}")
    
    # Read the SQL script
    with open(script_path, 'r') as f:
        sql_content = f.read()
    
    statements = _split_statements(sql_content)
    if not statements:
        logger.info(f"No executable statements in: {script_path.name}")
        return
    
    # Execute each statement sequentially in a single transaction
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
    
    logger.info(f"Completed SQL script: {script_path.name}")


def run_all_scripts(scripts_dir: Union[str, Path] = SQL_SCRIPTS_DIR, engine=None) -> None:
    """
    Run all SQL scripts in the specified directory in alphabetical order.
    
    Args:
        scripts_dir: Directory containing SQL scripts
        engine: SQLAlchemy engine to use (defaults to app engine)
    """
    scripts_dir = Path(scripts_dir)
    if not scripts_dir.exists():
        raise FileNotFoundError(f"SQL scripts directory not found: {scripts_dir}")
    
    # Get all .sql files in the directory
    sql_files = sorted([f for f in scripts_dir.glob("*.sql")])
    
    if not sql_files:
        logger.warning(f"No SQL scripts found in {scripts_dir}")
        return
    
    logger.info(f"Found {len(sql_files)} SQL scripts to run")
    
    # Run each script in order
    for script_path in sql_files:
        run_sql_script(script_path, engine)
    
    logger.info(f"All SQL scripts completed successfully")


def run_specific_scripts(script_names: List[str], scripts_dir: Union[str, Path] = SQL_SCRIPTS_DIR, engine=None) -> None:
    """
    Run specific SQL scripts by name.
    
    Args:
        script_names: List of script names to run
        scripts_dir: Directory containing SQL scripts
        engine: SQLAlchemy engine to use (defaults to app engine)
    """
    scripts_dir = Path(scripts_dir)
    if not scripts_dir.exists():
        raise FileNotFoundError(f"SQL scripts directory not found: {scripts_dir}")
    
    for script_name in script_names:
        # Ensure .sql extension
        if not script_name.endswith('.sql'):
            script_name = f"{script_name}.sql"
        
        script_path = scripts_dir / script_name
        run_sql_script(script_path, engine)


def main():
    """Command line interface for the SQL runner."""
    parser = argparse.ArgumentParser(description='Run SQL scripts for the Board Game Recommender')
    parser.add_argument('scripts', nargs='*', help='Specific SQL scripts to run (without .sql extension)')
    parser.add_argument('--all', action='store_true', help='Run all SQL scripts in the sql directory')
    parser.add_argument('--dir', help='Custom directory containing SQL scripts')
    
    args = parser.parse_args()
    
    scripts_dir = args.dir if args.dir else SQL_SCRIPTS_DIR
    
    try:
        if args.all:
            run_all_scripts(scripts_dir)
        elif args.scripts:
            run_specific_scripts(args.scripts, scripts_dir)
        else:
            parser.print_help()
    except Exception as e:
        logger.error(f"Error running SQL scripts: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
