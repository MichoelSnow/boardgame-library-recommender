"""Shared BoardGameGeek authentication helpers."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BGG_TOKEN_ENV_VAR = "BGG_TOKEN"


def get_bgg_token() -> str:
    """Return the configured BGG token, loading the repository dotenv file if needed."""
    token = os.getenv(BGG_TOKEN_ENV_VAR, "").strip()
    if token:
        return token

    repo_root_dotenv = Path(__file__).resolve().parents[3] / ".env"
    if repo_root_dotenv.exists():
        load_dotenv(dotenv_path=repo_root_dotenv, override=False)
        token = os.getenv(BGG_TOKEN_ENV_VAR, "").strip()
        if token:
            return token

    return ""


def build_bgg_auth_headers() -> dict[str, str]:
    """Build the authenticated request headers required by the BGG API."""
    token = get_bgg_token()
    if not token:
        raise ValueError(
            f"Missing required {BGG_TOKEN_ENV_VAR} environment variable for BGG API auth."
        )
    return {"Authorization": f"Bearer {token}"}
