#!/usr/bin/env python3
"""Shared resumable, checksum-verified ingestion artifact export."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Protocol


REPO_ROOT = Path(__file__).resolve().parents[2]
INGEST_ROOT = PurePosixPath("/app/data/ingest")
ARTIFACT_DESTINATIONS = {
    "ranks": "data/ingest/ranks",
    "game_data": "data/ingest/game_data",
    "ratings": "data/ingest/ratings",
}
MEGABYTE = 1024 * 1024


class ExportError(RuntimeError):
    """Expected operator-facing artifact export failure."""


class ArtifactSource(Protocol):
    """Operations needed by the shared transfer engine."""

    def size(self, remote_path: str) -> int: ...

    def sha256(self, remote_path: str) -> str: ...

    def read_chunk(
        self,
        remote_path: str,
        chunk_index: int,
        chunk_mb: int,
        expected_size: int,
        output_path: Path,
    ) -> None: ...


def artifact_relative_path(remote_path: str) -> PurePosixPath:
    path = PurePosixPath(remote_path)
    if not path.is_absolute() or INGEST_ROOT not in path.parents:
        raise ExportError(
            "artifact path must be under /app/data/ingest and identify a file"
        )
    if ".." in path.parts or path.name in {"", ".", ".."}:
        raise ExportError("artifact path is invalid")
    return path.relative_to("/app/data")


def artifact_output_dir(remote_path: str, override: str | None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    path = PurePosixPath(remote_path)
    for key, destination in ARTIFACT_DESTINATIONS.items():
        if f"/app/data/ingest/{key}/" in f"{path}/":
            return REPO_ROOT / destination
    # Preserve the legacy Fly helper's destination for explicitly selected
    # non-canonical files while keeping the three canonical paths automatic.
    return REPO_ROOT / "data/ingest/downloads"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _expected_chunk_size(total_size: int, chunk_index: int, chunk_bytes: int) -> int:
    offset = chunk_index * chunk_bytes
    remaining = total_size - offset
    if remaining <= 0:
        return 0
    return min(chunk_bytes, remaining)


def export_verified_artifact(
    source: ArtifactSource,
    remote_path: str,
    output_dir: str | Path | None = None,
    *,
    chunk_mb: int = 64,
    keep_parts: bool = False,
    overwrite: bool = False,
) -> Path:
    """Export one artifact, preserving resumable chunks until verification succeeds."""

    if chunk_mb <= 0:
        raise ExportError("chunk size must be greater than zero")

    relative_path = artifact_relative_path(remote_path)
    destination_dir = artifact_output_dir(
        remote_path, None if output_dir is None else str(output_dir)
    )
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / relative_path.name
    if destination.exists() and not overwrite:
        raise ExportError(
            f"refusing to overwrite existing artifact {destination}; use --overwrite"
        )

    remote_size = source.size(remote_path)
    if remote_size <= 0:
        raise ExportError("remote artifact size must be greater than zero")

    chunk_bytes = chunk_mb * MEGABYTE
    chunk_count = (remote_size + chunk_bytes - 1) // chunk_bytes
    parts_dir = destination_dir / f".{destination.name}.parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    temp_local = destination_dir / f".{destination.name}.tmp"

    print(f"Remote file: {remote_path}")
    print(f"Local file: {destination}")
    print(f"Remote size: {remote_size} bytes ({chunk_count} chunks)")

    try:
        for chunk_index in range(chunk_count):
            expected_size = _expected_chunk_size(
                remote_size, chunk_index, chunk_bytes
            )
            part_file = parts_dir / f"part_{chunk_index:06d}.bin"
            if part_file.is_file() and part_file.stat().st_size == expected_size:
                print(
                    f"Chunk {chunk_index + 1}/{chunk_count} already present "
                    f"({expected_size} bytes), skipping."
                )
                continue
            if part_file.exists():
                print(
                    f"Chunk {chunk_index + 1}/{chunk_count} has wrong size; "
                    "re-downloading."
                )
                part_file.unlink()

            temp_part = part_file.with_name(f"{part_file.name}.tmp")
            temp_part.unlink(missing_ok=True)
            print(f"Downloading chunk {chunk_index + 1}/{chunk_count}...")
            try:
                source.read_chunk(
                    remote_path,
                    chunk_index,
                    chunk_mb,
                    expected_size,
                    temp_part,
                )
                actual_size = temp_part.stat().st_size
                if actual_size != expected_size:
                    raise ExportError(
                        f"chunk {chunk_index} size mismatch after download "
                        f"({actual_size} != {expected_size})"
                    )
                os.replace(temp_part, part_file)
            finally:
                temp_part.unlink(missing_ok=True)

        temp_local.unlink(missing_ok=True)
        print(f"Reassembling chunks into {destination}...")
        with temp_local.open("wb") as assembled:
            for chunk_index in range(chunk_count):
                part_file = parts_dir / f"part_{chunk_index:06d}.bin"
                if not part_file.is_file():
                    raise ExportError(f"missing chunk file {part_file}")
                with part_file.open("rb") as chunk:
                    shutil.copyfileobj(chunk, assembled)

        assembled_size = temp_local.stat().st_size
        if assembled_size != remote_size:
            raise ExportError(
                f"assembled file size mismatch ({assembled_size} != {remote_size})"
            )

        print("Calculating remote SHA-256...")
        remote_sha = source.sha256(remote_path).lower()
        local_sha = _sha256_file(temp_local)
        print(f"Remote SHA-256: {remote_sha}")
        print(f"Local SHA-256:  {local_sha}")
        if remote_sha != local_sha:
            raise ExportError(
                "SHA-256 mismatch; keeping chunk directory for resume and "
                "investigation"
            )

        os.replace(temp_local, destination)
    except Exception:
        temp_local.unlink(missing_ok=True)
        raise

    if keep_parts:
        print(f"Chunk cache preserved: {parts_dir}")
    else:
        shutil.rmtree(parts_dir)
        print(f"Removed chunk cache: {parts_dir}")
    print(f"Export completed and verified: {destination}")
    return destination


class FlyArtifactSource:
    """Artifact source backed by the existing Fly SSH console interface."""

    def __init__(self, app_name: str):
        self.app_name = app_name

    def _command(self, command: str) -> list[str]:
        return [
            "fly",
            "ssh",
            "console",
            "-q",
            "-a",
            self.app_name,
            "-C",
            command,
        ]

    def size(self, remote_path: str) -> int:
        result = subprocess.run(
            self._command(f"stat -c %s {shlex.quote(remote_path)}"),
            check=True,
            text=True,
            capture_output=True,
        )
        for line in reversed(result.stdout.splitlines()):
            if line.strip().isdigit():
                return int(line.strip())
        raise ExportError(f"could not determine remote file size for {remote_path}")

    def sha256(self, remote_path: str) -> str:
        result = subprocess.run(
            self._command(f"sha256sum {shlex.quote(remote_path)}"),
            check=True,
            text=True,
            capture_output=True,
        )
        matches = re.findall(r"\b[a-fA-F0-9]{64}\b", result.stdout)
        if not matches:
            raise ExportError(f"failed to compute remote SHA-256 for {remote_path}")
        return matches[-1]

    def read_chunk(
        self,
        remote_path: str,
        chunk_index: int,
        chunk_mb: int,
        expected_size: int,
        output_path: Path,
    ) -> None:
        count_mb = (expected_size + MEGABYTE - 1) // MEGABYTE
        command = (
            f"dd if={shlex.quote(remote_path)} bs=1M "
            f"skip={chunk_index * chunk_mb} count={count_mb} status=none"
        )
        try:
            with output_path.open("wb") as output:
                subprocess.run(
                    self._command(command),
                    check=True,
                    stdout=output,
                    stderr=subprocess.PIPE,
                )
        except FileNotFoundError as exc:
            raise ExportError("fly CLI is not installed or not on PATH") from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or b"").decode(errors="replace").strip()
            raise ExportError(f"Fly chunk download failed: {detail}") from exc


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("fly",), required=True)
    parser.add_argument("--app", required=True)
    parser.add_argument("--remote-path", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--chunk-mb", type=int, default=64)
    parser.add_argument("--keep-parts", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        source = FlyArtifactSource(args.app)
        export_verified_artifact(
            source,
            args.remote_path,
            args.output_dir,
            chunk_mb=args.chunk_mb,
            keep_parts=args.keep_parts,
            overwrite=args.overwrite,
        )
    except (ExportError, OSError, subprocess.CalledProcessError) as exc:
        if isinstance(exc, subprocess.CalledProcessError):
            detail = (exc.stderr or exc.stdout or "").strip()
            print(f"Error: command failed: {detail}", file=sys.stderr)
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
