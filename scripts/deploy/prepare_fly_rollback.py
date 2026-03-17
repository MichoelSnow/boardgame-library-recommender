#!/usr/bin/env python3

import argparse
import json
import logging
import subprocess
import sys
from typing import Any

try:
    from validation_common import get_app_name, run_command
except ModuleNotFoundError:
    from scripts.validation_common import get_app_name, run_command


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def _get_release_field(release: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = release.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _get_release_version_label(release: dict[str, Any]) -> str:
    raw_version = _get_release_field(release, "Version", "version")
    if not raw_version:
        return "v?"
    version = raw_version.lower().lstrip("v")
    return f"v{version}"


def _get_release_status(release: dict[str, Any]) -> str:
    return _get_release_field(release, "Status", "status", default="unknown").lower()


def _get_release_image(release: dict[str, Any]) -> str:
    return _get_release_field(
        release, "ImageRef", "image_ref", "imageRef", "image", "docker_image"
    )


def _get_release_image_token(release: dict[str, Any]) -> str:
    image_ref = _get_release_image(release)
    if not image_ref:
        return "unknown"
    marker = "deployment-"
    if marker in image_ref:
        return image_ref.split(marker, 1)[1].strip() or "unknown"
    # Fallback if Fly returns an unexpected image format.
    return image_ref.rsplit(":", maxsplit=1)[-1].strip() or "unknown"


def _get_release_user_name(release: dict[str, Any]) -> str:
    user = release.get("User")
    if isinstance(user, dict):
        name = user.get("Name")
        if name:
            return str(name)
    return "unknown"


def load_releases(app_name: str) -> list[dict[str, Any]]:
    try:
        result = run_command(["fly", "releases", "-a", app_name, "--json", "--image"])
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise RuntimeError(
            f"Failed to query Fly releases for {app_name}: {stderr or exc}"
        ) from exc

    payload = json.loads(result.stdout)
    if not isinstance(payload, list):
        raise RuntimeError("Unexpected Fly release JSON payload format.")

    releases: list[dict[str, Any]] = []
    for item in payload:
        if isinstance(item, dict):
            releases.append(item)
    if not releases:
        raise RuntimeError("No Fly releases were found.")
    return releases


def resolve_rollback_target(
    releases: list[dict[str, Any]],
    target_release: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    current_release = releases[0]

    if target_release:
        normalized_target = f"v{target_release.lower().lstrip('v')}"
        for release in releases:
            version = _get_release_version_label(release)
            status = _get_release_status(release)
            if version == normalized_target:
                if status != "complete":
                    raise RuntimeError(
                        f"Requested rollback target {target_release} is not complete."
                    )
                return current_release, release
        raise RuntimeError(f"Requested rollback target {target_release} was not found.")

    for release in releases[1:]:
        status = _get_release_status(release)
        if status == "complete":
            return current_release, release

    raise RuntimeError("No previous complete Fly release is available for rollback.")


def log_recent_releases(releases: list[dict[str, Any]], limit: int) -> None:
    logger.info("Recent deployments (last %s):", max(limit, 1))
    for index, release in enumerate(releases[: max(limit, 1)], start=1):
        version = _get_release_version_label(release)
        release_id = _get_release_field(release, "ID", "id", default="unknown")
        status = _get_release_status(release)
        created_at = _get_release_field(
            release, "CreatedAt", "created_at", default="unknown"
        )
        description = _get_release_field(
            release, "Description", "description", default="unknown"
        )
        reason = _get_release_field(release, "Reason", "reason")
        image_token = _get_release_image_token(release)
        user_name = _get_release_user_name(release)
        reason_suffix = f", reason={reason}" if reason else ""
        logger.info(
            "%s) version=%s id=%s created_at=%s status=%s description=%s user=%s image_token=%s%s",
            index,
            version,
            release_id,
            created_at,
            status,
            description,
            user_name,
            image_token,
            reason_suffix,
        )


def default_config_file_for_environment(environment: str) -> str:
    if environment == "dev":
        return "fly.dev.toml"
    if environment == "prod":
        return "fly.toml"
    raise RuntimeError(f"Unsupported environment: {environment}")


def prepare_rollback(
    environment: str,
    target_release: str | None,
    limit: int,
    config_file: str,
) -> int:
    app_name = get_app_name(environment)
    releases = load_releases(app_name)
    current_release, rollback_target = resolve_rollback_target(releases, target_release)
    rollback_target_version = _get_release_version_label(rollback_target)
    rollback_target_token = _get_release_image_token(rollback_target)
    if rollback_target_token == "unknown":
        raise RuntimeError(
            f"Could not find image reference for rollback target {rollback_target_version}."
        )

    logger.info("Environment: %s", environment)
    logger.info("Current Fly release: %s", _get_release_version_label(current_release))
    logger.info("Rollback target: %s", rollback_target_version)
    logger.info("Rollback target image token: %s", rollback_target_token)
    log_recent_releases(releases, limit)
    logger.info(
        "Example command (edit token as needed): fly deploy -c %s --image registry.fly.io/%s:deployment-%s -a %s",
        config_file,
        app_name,
        rollback_target_token,
        app_name,
    )
    logger.info("Rollback path validation passed.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve and print the safe Fly rollback command."
    )
    parser.add_argument(
        "--env",
        choices=["dev", "prod"],
        required=True,
        help="Target Fly environment to inspect.",
    )
    parser.add_argument(
        "--target-release",
        help="Optional explicit Fly release version to use as the rollback target.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of recent deployments to print (default: 10).",
    )
    parser.add_argument(
        "--config-file",
        default="",
        help="Fly config file to use in rollback command output. Defaults by env (dev=fly.dev.toml, prod=fly.toml).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config_file = args.config_file or default_config_file_for_environment(args.env)
        return prepare_rollback(args.env, args.target_release, args.limit, config_file)
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
