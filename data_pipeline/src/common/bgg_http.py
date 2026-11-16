"""Shared authenticated BoardGameGeek HTTP helpers."""

from __future__ import annotations

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .bgg_auth import build_bgg_auth_headers


DEFAULT_BGG_REQUEST_TIMEOUT_SECONDS = 20


@retry(
    retry=retry_if_exception_type(requests.RequestException),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
def request_bgg_xml(
    url: str,
    *,
    timeout_seconds: int = DEFAULT_BGG_REQUEST_TIMEOUT_SECONDS,
) -> requests.Response:
    """Fetch an authenticated BGG XML response with bounded retries."""
    response = requests.get(
        url,
        headers=build_bgg_auth_headers(),
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    return response
