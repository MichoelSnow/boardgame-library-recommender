#!/usr/bin/env python3

import argparse
import json
import logging
import os
import shlex
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class FileSyncItem:
    relative_path: str
    local_path: Path
    remote_path: str
    local_size: int
    remote_size: int | None


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Synchronize local files to a Fly machine path via fly ssh sftp put, "
            "uploading only files that are missing remotely or have size mismatches."
        )
    )
    parser.add_argument("--app", required=True, help="Fly app name.")
    parser.add_argument(
        "--local-dir",
        required=True,
        help="Local source directory containing files to sync.",
    )
    parser.add_argument(
        "--remote-dir",
        required=True,
        help="Remote destination directory on Fly machine (e.g. /data/images/full).",
    )
    parser.add_argument(
        "--state-file",
        default=".tmp/fly_sftp_sync_state.json",
        help="JSON state file tracking completed uploads for resume support.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max number of files to upload this run (0 = no limit).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute and log actions without uploading files.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=250,
        help="Number of files per SFTP recursive upload batch.",
    )
    parser.add_argument(
        "--staging-dir",
        default=".tmp/fly_sftp_sync_staging",
        help="Local temp directory used for upload batch staging.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args()


@retry(
    retry=retry_if_exception_type(subprocess.CalledProcessError),
    stop=stop_after_attempt(3),
    wait=wait_fixed(2),
    reraise=True,
)
def run_command(command: list[str], *, capture_output: bool = False) -> str:
    LOGGER.debug("Running command: %s", " ".join(shlex.quote(p) for p in command))
    result = subprocess.run(
        command,
        check=True,
        capture_output=capture_output,
        text=True,
    )
    if capture_output:
        return result.stdout
    return ""


def build_local_manifest(local_dir: Path) -> dict[str, int]:
    if not local_dir.exists():
        raise FileNotFoundError(f"Local directory not found: {local_dir}")
    if not local_dir.is_dir():
        raise ValueError(f"Local path must be a directory: {local_dir}")

    manifest: dict[str, int] = {}
    for file_path in sorted(local_dir.rglob("*")):
        if not file_path.is_file():
            continue
        relative_path = file_path.relative_to(local_dir).as_posix()
        manifest[relative_path] = file_path.stat().st_size
    return manifest


def parse_remote_manifest(raw_text: str) -> dict[str, int]:
    manifest: dict[str, int] = {}
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "|" not in line:
            continue
        relative_path, size_raw = line.rsplit("|", 1)
        relative_path = relative_path.strip()
        size_raw = size_raw.strip()
        if not relative_path:
            continue
        try:
            manifest[relative_path] = int(size_raw)
        except ValueError:
            continue
    return manifest


def fetch_remote_manifest(app_name: str, remote_dir: str) -> dict[str, int]:
    quoted_remote_dir = shlex.quote(remote_dir)
    remote_command = "sh -lc " + shlex.quote(
        f"if [ -d {quoted_remote_dir} ]; then "
        f'find {quoted_remote_dir} -type f -printf "%P|%s\\n" | sort; '
        "fi"
    )
    stdout = run_command(
        ["fly", "ssh", "console", "-a", app_name, "-C", remote_command],
        capture_output=True,
    )
    return parse_remote_manifest(stdout)


def build_sync_plan(
    local_manifest: dict[str, int],
    remote_manifest: dict[str, int],
    local_dir: Path,
    remote_dir: str,
) -> list[FileSyncItem]:
    plan: list[FileSyncItem] = []
    remote_root = remote_dir.rstrip("/")
    for relative_path in sorted(local_manifest):
        local_size = local_manifest[relative_path]
        remote_size = remote_manifest.get(relative_path)
        if remote_size == local_size:
            continue
        plan.append(
            FileSyncItem(
                relative_path=relative_path,
                local_path=local_dir / relative_path,
                remote_path=f"{remote_root}/{relative_path}",
                local_size=local_size,
                remote_size=remote_size,
            )
        )
    return plan


def load_state(state_file: Path) -> set[str]:
    if not state_file.exists():
        return set()
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    completed = data.get("completed", [])
    if not isinstance(completed, list):
        return set()
    return {str(item) for item in completed}


def save_state(state_file: Path, completed: set[str]) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {"completed": sorted(completed)}
    state_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def retain_relevant_completed(
    completed: set[str],
    sync_plan: list[FileSyncItem],
) -> set[str]:
    """
    Keep only completed records still relevant to the current local-vs-remote plan.

    Upload decisions are based on live remote manifest diff. Completed state is
    retained for progress visibility only and must never suppress required uploads.
    """
    pending_paths = {item.relative_path for item in sync_plan}
    return completed.intersection(pending_paths)


def chunked(items: list[FileSyncItem], batch_size: int) -> list[list[FileSyncItem]]:
    if batch_size <= 0:
        raise ValueError("--batch-size must be >= 1")
    return [items[i : i + batch_size] for i in range(0, len(items), batch_size)]


@retry(
    retry=retry_if_exception_type(subprocess.CalledProcessError),
    stop=stop_after_attempt(3),
    wait=wait_fixed(2),
    reraise=True,
)
def ensure_remote_directory(app_name: str, directory_path: str) -> None:
    command = [
        "fly",
        "ssh",
        "console",
        "-a",
        app_name,
        "-C",
        "sh -lc " + shlex.quote(f"mkdir -p {shlex.quote(directory_path)}"),
    ]
    run_command(command, capture_output=False)


def stage_batch_files(
    batch_items: list[FileSyncItem],
    local_dir: Path,
    remote_leaf: str,
    staging_root: Path,
) -> Path:
    staging_root.mkdir(parents=True, exist_ok=True)
    batch_root = Path(tempfile.mkdtemp(prefix="batch_", dir=staging_root))
    staged_leaf_root = batch_root / remote_leaf
    staged_leaf_root.mkdir(parents=True, exist_ok=True)

    for item in batch_items:
        relative_path = Path(item.relative_path)
        staged_path = staged_leaf_root / relative_path
        staged_path.parent.mkdir(parents=True, exist_ok=True)
        source_path = local_dir / relative_path
        try:
            os.link(source_path, staged_path)
        except OSError:
            shutil.copy2(source_path, staged_path)

    return batch_root


def upload_batch_directory(
    app_name: str,
    local_batch_dir: Path,
    remote_destination_dir: str,
) -> None:
    run_command(
        [
            "fly",
            "ssh",
            "sftp",
            "put",
            "-R",
            "-a",
            app_name,
            str(local_batch_dir),
            remote_destination_dir,
        ],
        capture_output=False,
    )


@retry(
    retry=retry_if_exception_type(subprocess.CalledProcessError),
    stop=stop_after_attempt(3),
    wait=wait_fixed(2),
    reraise=True,
)
def merge_remote_staging_directory(
    app_name: str,
    staged_remote_dir: str,
    remote_dir: str,
) -> None:
    remote_command = "sh -lc " + shlex.quote(
        f"mkdir -p {shlex.quote(remote_dir)} "
        f"&& cp -a {shlex.quote(staged_remote_dir)}/. {shlex.quote(remote_dir)}/ "
        f"&& rm -rf {shlex.quote(staged_remote_dir)}"
    )
    run_command(
        [
            "fly",
            "ssh",
            "console",
            "-a",
            app_name,
            "-C",
            remote_command,
        ],
        capture_output=False,
    )


@retry(
    retry=retry_if_exception_type(subprocess.CalledProcessError),
    stop=stop_after_attempt(3),
    wait=wait_fixed(2),
    reraise=True,
)
def remove_remote_directory_if_exists(app_name: str, directory_path: str) -> None:
    remote_command = "sh -lc " + shlex.quote(f"rm -rf {shlex.quote(directory_path)}")
    run_command(
        [
            "fly",
            "ssh",
            "console",
            "-a",
            app_name,
            "-C",
            remote_command,
        ],
        capture_output=False,
    )


@retry(
    retry=retry_if_exception_type(subprocess.CalledProcessError),
    stop=stop_after_attempt(3),
    wait=wait_fixed(2),
    reraise=True,
)
def clear_remote_staging_root(app_name: str, staging_root: str) -> None:
    remote_command = "sh -lc " + shlex.quote(
        f"mkdir -p {shlex.quote(staging_root)} "
        f"&& find {shlex.quote(staging_root)} -mindepth 1 -maxdepth 1 -exec rm -rf -- {{}} +"
    )
    run_command(
        [
            "fly",
            "ssh",
            "console",
            "-a",
            app_name,
            "-C",
            remote_command,
        ],
        capture_output=False,
    )


def main() -> int:
    args = parse_args()
    configure_logging(args.verbose)

    local_dir = Path(args.local_dir).expanduser().resolve()
    remote_dir = args.remote_dir.strip()
    if not remote_dir.startswith("/"):
        raise ValueError("--remote-dir must be an absolute path.")

    state_file = Path(args.state_file).expanduser().resolve()
    completed = load_state(state_file)

    LOGGER.info("Building local manifest from %s", local_dir)
    local_manifest = build_local_manifest(local_dir)
    LOGGER.info("Local files discovered: %d", len(local_manifest))

    LOGGER.info("Fetching remote manifest from app=%s path=%s", args.app, remote_dir)
    remote_manifest = fetch_remote_manifest(args.app, remote_dir)
    LOGGER.info("Remote files discovered: %d", len(remote_manifest))

    sync_plan = build_sync_plan(local_manifest, remote_manifest, local_dir, remote_dir)
    LOGGER.info("Files requiring upload: %d", len(sync_plan))
    if not sync_plan:
        return 0

    if completed:
        original_count = len(completed)
        completed = retain_relevant_completed(completed, sync_plan)
        if len(completed) != original_count:
            save_state(state_file, completed)
        LOGGER.info(
            "State file has %d relevant completed records (not used to suppress uploads).",
            len(completed),
        )

    if args.limit > 0:
        sync_plan = sync_plan[: args.limit]
        LOGGER.info(
            "Applying --limit=%d, upload set reduced to %d", args.limit, len(sync_plan)
        )

    if args.dry_run:
        for item in sync_plan[:50]:
            LOGGER.info(
                "DRY RUN upload: %s (local=%d, remote=%s)",
                item.relative_path,
                item.local_size,
                "missing" if item.remote_size is None else str(item.remote_size),
            )
        if len(sync_plan) > 50:
            LOGGER.info("DRY RUN truncated output at 50 files.")
        return 0

    remote_path = Path(remote_dir)
    remote_parent_dir = remote_path.parent.as_posix() or "/"
    remote_leaf = remote_path.name
    ensure_remote_directory(args.app, remote_parent_dir)
    remote_stage_parent = "/data/.fly_sftp_sync_stage"
    ensure_remote_directory(args.app, remote_stage_parent)
    LOGGER.info("Clearing stale remote staging dirs under %s", remote_stage_parent)
    clear_remote_staging_root(args.app, remote_stage_parent)

    staging_root = Path(args.staging_dir).expanduser().resolve()
    staging_root.mkdir(parents=True, exist_ok=True)

    uploaded_count = 0
    batches = chunked(sync_plan, args.batch_size)
    LOGGER.info(
        "Uploading in %d batch(es) with batch size %d",
        len(batches),
        args.batch_size,
    )

    for index, batch_items in enumerate(batches, start=1):
        LOGGER.info(
            "Uploading batch %d/%d (%d files)",
            index,
            len(batches),
            len(batch_items),
        )
        batch_leaf_name = f"{remote_leaf}__batch_{index:05d}"
        batch_root = stage_batch_files(
            batch_items, local_dir, batch_leaf_name, staging_root
        )
        local_batch_dir = batch_root / batch_leaf_name
        remote_staged_batch_dir = f"{remote_stage_parent}/{batch_leaf_name}"
        try:
            remove_remote_directory_if_exists(args.app, remote_staged_batch_dir)
            upload_batch_directory(args.app, local_batch_dir, remote_staged_batch_dir)
            merge_remote_staging_directory(
                args.app, remote_staged_batch_dir, remote_dir
            )
        finally:
            shutil.rmtree(batch_root, ignore_errors=True)

        for item in batch_items:
            completed.add(item.relative_path)
        save_state(state_file, completed)
        uploaded_count += len(batch_items)
        LOGGER.info("Uploaded %d/%d files", uploaded_count, len(sync_plan))

    LOGGER.info("Upload complete. Uploaded %d files.", uploaded_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
