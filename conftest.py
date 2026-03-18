"""Pytest bootstrap for stable in-repo imports."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
repo_root_str = str(REPO_ROOT)
if repo_root_str not in sys.path:
    sys.path.insert(0, repo_root_str)

# Force test runs to use the in-repo SQLite DB even when a shell-level
# Postgres DATABASE_URL is exported.
TEST_SQLITE_URL = f"sqlite:///{REPO_ROOT / 'backend' / 'database' / 'boardgames.db'}"
os.environ["DATABASE_URL"] = TEST_SQLITE_URL
os.environ.setdefault("NODE_ENV", "test")

existing = sys.modules.get("data_pipeline")
if existing is not None:
    existing_file = str(getattr(existing, "__file__", ""))
    if not existing_file.startswith(repo_root_str):
        for module_name in list(sys.modules):
            if module_name == "data_pipeline" or module_name.startswith(
                "data_pipeline."
            ):
                sys.modules.pop(module_name, None)

importlib.import_module("data_pipeline")
importlib.import_module("data_pipeline.src")
importlib.import_module("data_pipeline.tests")
