#!/usr/bin/env python3

import json
import logging
import os
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:

    def load_dotenv(dotenv_path=None, *args, **kwargs):
        path = dotenv_path or ".env"
        env_path = Path(path)
        if not env_path.exists():
            return False

        loaded = False
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
                loaded = True
        return loaded


try:
    from tenacity import (
        retry,
        retry_if_exception,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
    )
except ImportError:

    def retry(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

    def retry_if_exception_type(*args, **kwargs):
        return None

    def retry_if_exception(*args, **kwargs):
        return None

    def stop_after_attempt(*args, **kwargs):
        return None

    def wait_exponential(*args, **kwargs):
        return None


load_dotenv()

logger = logging.getLogger(__name__)

APP_CONFIG = {
    "local": {
        "app_name": "local",
        "base_url": os.getenv("LOCAL_APP_BASE_URL", "http://127.0.0.1:8000"),
    },
    "dev": {
        "app_name": "pax-tt-app-dev",
        "base_url": "https://pax-tt-app-dev.fly.dev",
    },
    "prod": {
        "app_name": "pax-tt-app",
        "base_url": "https://pax-tt-app.fly.dev",
    },
}


def _is_retryable_http_error(exc: BaseException) -> bool:
    if not isinstance(exc, urllib.error.HTTPError):
        return False
    return exc.code == 429 or 500 <= exc.code <= 599


RETRYABLE_EXCEPTIONS = (
    urllib.error.URLError,
    TimeoutError,
)


def _build_retry_condition():
    retry_on_exception_type = retry_if_exception_type(RETRYABLE_EXCEPTIONS)
    retry_on_retryable_http = retry_if_exception(_is_retryable_http_error)
    if retry_on_exception_type is None:
        return retry_on_retryable_http
    if retry_on_retryable_http is None:
        return retry_on_exception_type
    return retry_on_exception_type | retry_on_retryable_http


def get_base_url(environment: str) -> str:
    return APP_CONFIG[environment]["base_url"]


def get_app_name(environment: str) -> str:
    return APP_CONFIG[environment]["app_name"]


def build_url(environment: str, path: str, query: dict[str, Any] | None = None) -> str:
    base_url = get_base_url(environment)
    if not path.startswith("/"):
        path = f"/{path}"
    url = f"{base_url}{path}"
    if query:
        encoded_query = urllib.parse.urlencode(query)
        url = f"{url}?{encoded_query}"
    return url


def _decode_response(response: Any) -> Any:
    content_type = response.headers.get("Content-Type", "")
    body = response.read()
    if "application/json" in content_type:
        return json.loads(body.decode("utf-8"))
    return body.decode("utf-8")


def request_once(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: int = 15,
) -> tuple[Any, dict[str, str]]:
    request = urllib.request.Request(
        url=url,
        method=method,
        headers=headers or {},
        data=data,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = _decode_response(response)
        response_headers = dict(response.headers.items())
    return payload, response_headers


@retry(
    retry=_build_retry_condition(),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
)
def request_with_retry(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: int = 15,
) -> tuple[Any, dict[str, str]]:
    return request_once(
        url,
        method=method,
        headers=headers,
        data=data,
        timeout=timeout,
    )


def fetch_json(
    url: str, *, headers: dict[str, str] | None = None
) -> tuple[dict, dict[str, str]]:
    payload, response_headers = request_with_retry(url, headers=headers)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object response from {url}.")
    return payload, response_headers


def fetch_json_once(
    url: str, *, headers: dict[str, str] | None = None
) -> tuple[Any, dict[str, str]]:
    payload, response_headers = request_once(url, headers=headers)
    return payload, response_headers


def post_form_json(
    url: str,
    form_data: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
) -> tuple[dict, dict[str, str]]:
    merged_headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }
    if headers:
        merged_headers.update(headers)

    payload, response_headers = request_with_retry(
        url,
        method="POST",
        headers=merged_headers,
        data=urllib.parse.urlencode(form_data).encode("utf-8"),
    )
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object response from {url}.")
    return payload, response_headers


def measure_json_request(
    url: str, *, headers: dict[str, str] | None = None
) -> tuple[Any, float]:
    started = time.perf_counter()
    payload, _ = fetch_json_once(url, headers=headers)
    duration_ms = (time.perf_counter() - started) * 1000
    return payload, duration_ms


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )


def resolve_smoke_test_credentials(
    environment: str,
    username: str | None = None,
    password: str | None = None,
) -> tuple[str | None, str | None]:
    env_key = environment.upper()
    resolved_username = username or os.getenv("SMOKE_TEST_USERNAME")
    resolved_password = (
        password
        or os.getenv(f"SMOKE_TEST_PASSWORD_{env_key}")
        or os.getenv("SMOKE_TEST_PASSWORD")
    )
    return resolved_username, resolved_password
