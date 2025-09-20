# Post-Import SQL Scripts

This directory contains SQL scripts that are run after data import to perform calculations and updates on the database.

## Script Naming Convention

Scripts are executed in alphabetical order, so they should be named with a numeric prefix to control the execution order:

- `01_calculate_avg_box_volume.sql` - Calculates and updates the average box volume for all games
- `02_another_calculation.sql` - Another calculation script (example)
- etc.

## How to Add a New Script

1. Create a new SQL file in this directory with a numeric prefix
2. Write your SQL statements in the file
3. The script will be automatically run after data import when `--delete-existing` is used
4. You can also run it manually using the `run_post_import.py` script

## Running Scripts Manually

You can run the SQL scripts manually using the `run_post_import.py` script:

```bash
# Run all SQL scripts
python backend/scripts/run_post_import.py

# Run a specific SQL script (without .sql extension)
python backend/scripts/run_post_import.py --script 01_calculate_avg_box_volume

# List available SQL scripts
python backend/scripts/run_post_import.py --list
```

Or you can use the more general `sql_runner.py` script:

```bash
# Run all SQL scripts
python backend/scripts/sql_runner.py --all

# Run specific SQL scripts
python backend/scripts/sql_runner.py 01_calculate_avg_box_volume 02_another_calculation
```

## Integration with Import Process

The SQL scripts are automatically run after data import when the `--delete-existing` flag is used:

```bash
python backend/app/import_data.py --delete-existing
```

This ensures that calculated fields are properly updated after a full data import.
