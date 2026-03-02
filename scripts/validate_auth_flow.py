#!/usr/bin/env python3

import argparse
import logging
import sys
import urllib.error

from validation_common import (
    build_url,
    fetch_json,
    request_once,
    resolve_smoke_test_credentials,
    post_form_json,
)


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def validate_unauthenticated_rejection(environment: str) -> None:
    url = build_url(environment, "/api/users/me/")
    try:
        request_once(url)
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            logger.info("Unauthenticated access is rejected as expected.")
            return
        raise RuntimeError(
            f"Protected endpoint returned unexpected status: HTTP {exc.code}"
        ) from exc

    raise RuntimeError("Protected endpoint unexpectedly allowed unauthenticated access.")


def validate_login_success(environment: str, username: str, password: str) -> None:
    token_url = build_url(environment, "/api/token")
    try:
        token_payload, _ = post_form_json(
            token_url,
            {
                "grant_type": "password",
                "username": username,
                "password": password,
            },
        )
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 401):
            raise RuntimeError(
                "Smoke-test login failed. "
                "Check that the smoke-test user exists in this environment and that "
                "the configured password matches the database record."
            ) from exc
        raise RuntimeError(
            f"Token endpoint returned unexpected status during smoke-test login: HTTP {exc.code}"
        ) from exc
    access_token = token_payload.get("access_token")
    if not access_token:
        raise RuntimeError("Token endpoint did not return an access token.")

    user_payload, _ = fetch_json(
        build_url(environment, "/api/users/me/"),
        headers={"Authorization": f"Bearer {access_token}"},
    )

    if user_payload.get("username") != username:
        raise RuntimeError(
            "Authenticated user payload did not match the expected username."
        )
    if not user_payload.get("is_active", False):
        raise RuntimeError("Authenticated user is not active.")

    logger.info("Authenticated login flow passed for user: %s", username)


def validate_auth_flow(
    environment: str,
    username: str | None = None,
    password: str | None = None,
) -> int:
    resolved_username, resolved_password = resolve_smoke_test_credentials(
        environment,
        username=username,
        password=password,
    )

    logger.info("Environment: %s", environment)
    validate_unauthenticated_rejection(environment)

    if resolved_username and resolved_password:
        validate_login_success(environment, resolved_username, resolved_password)
    else:
        logger.warning(
            "Environment-specific smoke-test credentials are not set. "
            "Skipped positive login smoke test and validated only unauthorized rejection."
        )

    logger.info("Auth flow smoke test passed.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate auth behavior for a Fly environment."
    )
    parser.add_argument(
        "--env",
        choices=["local", "dev", "prod"],
        required=True,
        help="Target Fly environment to validate.",
    )
    parser.add_argument(
        "--username",
        help="Optional smoke-test username. Falls back to environment-specific .env vars.",
    )
    parser.add_argument(
        "--password",
        help="Optional smoke-test password. Falls back to environment-specific .env vars.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return validate_auth_flow(
            args.env,
            username=args.username,
            password=args.password,
        )
    except Exception as exc:
        logger.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
