#!/usr/bin/env python3

import argparse
from datetime import datetime, timezone
import logging
import subprocess
import sys
from pathlib import PurePosixPath


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


APP_NAMES = {
    "dev": "pax-tt-app-dev",
    "prod": "pax-tt-app",
}


def run_fly_ls(app_name: str) -> list[str]:
    command = [
        "fly",
        "ssh",
        "console",
        "-a",
        app_name,
        "-C",
        'sh -lc "ls -1 /data/game_embeddings_*.npz /data/reverse_mappings_*.json"',
    ]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise RuntimeError(
            f"Failed to inspect recommendation artifacts for {app_name}: {stderr}"
        ) from exc

    paths = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("Connecting to "):
            continue
        paths.append(stripped)
    return paths


def extract_timestamp(path_str: str, prefix: str) -> str | None:
    stem = PurePosixPath(path_str).stem
    expected_prefix = f"{prefix}_"
    if not stem.startswith(expected_prefix):
        return None
    return stem[len(expected_prefix) :]


def format_timestamp(timestamp: str) -> str:
    try:
        timestamp_int = int(timestamp)
    except ValueError:
        return "unparseable"

    return datetime.fromtimestamp(timestamp_int, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def validate_artifacts(environment: str) -> int:
    app_name = APP_NAMES[environment]
    paths = run_fly_ls(app_name)

    embedding_paths = sorted(
        path
        for path in paths
        if PurePosixPath(path).name.startswith("game_embeddings_")
    )
    mapping_paths = sorted(
        path
        for path in paths
        if PurePosixPath(path).name.startswith("reverse_mappings_")
    )

    if not embedding_paths:
        logger.error("No game_embeddings artifacts found in %s.", app_name)
        return 1
    if not mapping_paths:
        logger.error("No reverse_mappings artifacts found in %s.", app_name)
        return 1

    mappings_by_timestamp = {}
    for path in mapping_paths:
        timestamp = extract_timestamp(path, "reverse_mappings")
        if timestamp:
            mappings_by_timestamp[timestamp] = path

    matched_pairs = []
    for path in embedding_paths:
        timestamp = extract_timestamp(path, "game_embeddings")
        if not timestamp:
            continue
        mapping_path = mappings_by_timestamp.get(timestamp)
        if mapping_path:
            matched_pairs.append((timestamp, path, mapping_path))

    logger.info("Environment: %s", environment)
    logger.info("Embedding files found: %d", len(embedding_paths))
    logger.info("Mapping files found: %d", len(mapping_paths))

    if not matched_pairs:
        logger.error("No matched embeddings/reverse_mappings timestamp pairs found.")
        return 1

    matched_pairs.sort(key=lambda item: item[0])
    latest_timestamp, latest_embedding_path, latest_mapping_path = matched_pairs[-1]
    logger.info("Matched pairs found: %d", len(matched_pairs))
    logger.info("Newest matched timestamp: %s", latest_timestamp)
    logger.info(
        "Newest matched timestamp (UTC): %s", format_timestamp(latest_timestamp)
    )
    logger.info("Embedding: %s", latest_embedding_path)
    logger.info("Mapping: %s", latest_mapping_path)
    logger.info(
        "Artifact file validation passed. "
        "Review startup logs manually only when deploy/config changes warrant it."
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate Fly recommendation artifact files for dev or prod."
    )
    parser.add_argument(
        "--env",
        choices=sorted(APP_NAMES.keys()),
        required=True,
        help="Target Fly environment to validate.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return validate_artifacts(args.env)
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
