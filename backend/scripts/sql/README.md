# Post-Import SQL Scripts

This directory contains SQL scripts that are run after data import to perform calculations and updates on the database.

## Script Naming Convention

Scripts are executed in alphabetical order, so they should be named with a numeric prefix to control the execution order (for example `01_...sql`, `02_...sql`).

## How to Add a New Script

1. Create a new SQL file in this directory with a numeric prefix
2. Write your SQL statements in the file
3. The script will be automatically run after data import when `--delete-existing` is used
4. You can also run scripts manually with `sql_runner.py`.

## Running Scripts Manually

Use `sql_runner.py`:

```bash
# Run all SQL scripts
python backend/scripts/sql_runner.py --all

# Run specific SQL scripts
python backend/scripts/sql_runner.py 01_some_script 02_another_script
```

## Integration with Import Process

The SQL scripts are automatically run after data import when the `--delete-existing` flag is used:

```bash
python backend/app/import_data.py --delete-existing
```

This ensures that calculated fields are properly updated after a full data import.
