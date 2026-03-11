#!/usr/bin/env python3

import argparse
import json
import logging
import os
import sys

try:
    from validation_common import (
        APP_CONFIG,
        build_url,
        post_form_json,
        request_with_retry,
        resolve_smoke_test_credentials,
    )
except ModuleNotFoundError:
    from scripts.validation_common import (
        APP_CONFIG,
        build_url,
        post_form_json,
        request_with_retry,
        resolve_smoke_test_credentials,
    )


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def resolve_admin_credentials() -> tuple[str | None, str | None]:
    return os.getenv("ADMIN_USERNAME"), os.getenv("ADMIN_PASSWORD")


def create_smoke_test_user(
    environment: str,
    username: str | None = None,
    password: str | None = None,
) -> int:
    if environment not in APP_CONFIG:
        raise RuntimeError(f"Invalid environment: {environment}")

    admin_username, admin_password = resolve_admin_credentials()
    if not admin_username or not admin_password:
        raise RuntimeError(
            "ADMIN_USERNAME and ADMIN_PASSWORD must be set before creating the smoke-test user."
        )

    smoke_username, smoke_password = resolve_smoke_test_credentials(
        environment,
        username=username,
        password=password,
    )
    if not smoke_username or not smoke_password:
        raise RuntimeError(
            "SMOKE_TEST_USERNAME and the environment-specific SMOKE_TEST_PASSWORD must be set."
        )

    token_payload, _ = post_form_json(
        build_url(environment, "/api/token"),
        {
            "grant_type": "password",
            "username": admin_username,
            "password": admin_password,
        },
    )
    access_token = token_payload.get("access_token")
    if not access_token:
        raise RuntimeError("Admin token request did not return an access token.")

    try:
        user_payload, _ = request_with_retry(
            build_url(environment, "/api/users/"),
            method="POST",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            data=json.dumps(
                {
                    "username": smoke_username,
                    "password": smoke_password,
                    "is_admin": False,
                }
            ).encode("utf-8"),
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to create smoke-test user: {exc}") from exc

    if not isinstance(user_payload, dict):
        raise RuntimeError("Smoke-test user creation did not return a JSON object.")

    logger.info(
        "Created smoke-test user in %s: %s", environment, user_payload.get("username")
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create the smoke-test user in a target environment."
    )
    parser.add_argument(
        "--env",
        choices=["local", "dev", "prod"],
        required=True,
        help="Target environment.",
    )
    parser.add_argument(
        "--username",
        help="Optional override for the shared smoke-test username.",
    )
    parser.add_argument(
        "--password",
        help="Optional override for the environment-specific smoke-test password.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return create_smoke_test_user(
            args.env,
            username=args.username,
            password=args.password,
        )
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
