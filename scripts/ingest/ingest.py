#!/usr/bin/env python3
"""Provider-neutral operator interface for the Docker ingestion workflow."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Sequence

from dotenv import dotenv_values

try:
    from scripts.ingest.artifact_export import (
        ExportError,
        MEGABYTE,
        artifact_output_dir,
        artifact_relative_path,
        export_verified_artifact,
    )
except ModuleNotFoundError:  # Direct execution: python scripts/ingest/ingest.py
    from artifact_export import (  # type: ignore[no-redef]
        ExportError,
        MEGABYTE,
        artifact_output_dir,
        artifact_relative_path,
        export_verified_artifact,
    )


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE_OPTIONS = {
    "ranks": "get_ranks",
    "game-data": "get_game_data",
    "ratings": "get_ratings",
}
DOCKER_CLIENT_ENV_VARS = {
    "DOCKER_CONTEXT",
    "DOCKER_HOST",
    "DOCKER_TLS_VERIFY",
    "DOCKER_CERT_PATH",
}


class OperatorError(RuntimeError):
    """Expected operator-facing failure."""


@dataclass(frozen=True)
class Profile:
    target: str
    image: str
    container_name: str
    local_workspace: Path
    remote_host: str | None
    remote_workspace: str
    remote_workspace_type: str
    env_file: Path | None

    @property
    def workspace_label(self) -> str:
        if self.target == "local":
            return str(self.local_workspace)
        return self.remote_workspace


def _env_path(name: str, default: Path | None = None) -> Path | None:
    value = os.getenv(name, "").strip()
    if value:
        return Path(value).expanduser().resolve()
    return default


def build_profile(args: argparse.Namespace) -> Profile:
    target = args.target or os.getenv("INGEST_TARGET", "").strip()
    if target not in {"local", "remote", "fly"}:
        raise OperatorError("select a target with --target local, remote, or fly")

    image = args.image or os.getenv("INGEST_IMAGE", "bg-lib-ingest:current")
    container_name = args.container_name or os.getenv(
        "INGEST_CONTAINER_NAME", f"bg-lib-ingest-{target}"
    )
    env_file = args.env_file or _env_path("INGEST_ENV_FILE", REPO_ROOT / ".env")
    if env_file is not None:
        env_file = Path(env_file).expanduser().resolve()
    if env_file is not None and not env_file.exists():
        env_file = None

    local_workspace = (
        Path(args.local_workspace).expanduser().resolve()
        if args.local_workspace
        else _env_path("INGEST_LOCAL_WORKSPACE", REPO_ROOT / "data")
    )
    assert local_workspace is not None

    remote_host = args.remote_host or os.getenv("INGEST_REMOTE_DOCKER_HOST", "").strip()
    if target == "remote":
        if not remote_host:
            raise OperatorError(
                "remote target requires --remote-host or INGEST_REMOTE_DOCKER_HOST"
            )
        if not remote_host.startswith("ssh://"):
            remote_host = f"ssh://{remote_host}"

    remote_workspace = args.remote_workspace or os.getenv(
        "INGEST_REMOTE_WORKSPACE", "bg-lib-ingest-data"
    )
    remote_workspace_type = args.remote_workspace_type or os.getenv(
        "INGEST_REMOTE_WORKSPACE_TYPE", "volume"
    )
    if remote_workspace_type not in {"volume", "bind"}:
        raise OperatorError("remote workspace type must be 'volume' or 'bind'")
    if (
        target == "remote"
        and remote_workspace_type == "bind"
        and not remote_workspace.startswith("/")
    ):
        raise OperatorError("remote bind workspace must be an absolute remote path")

    return Profile(
        target=target,
        image=image,
        container_name=container_name,
        local_workspace=local_workspace,
        remote_host=remote_host,
        remote_workspace=remote_workspace,
        remote_workspace_type=remote_workspace_type,
        env_file=env_file,
    )


def docker_environment(profile: Profile) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("DOCKER_CONTEXT", None)
    if profile.target == "remote":
        assert profile.remote_host is not None
        environment["DOCKER_HOST"] = profile.remote_host
    else:
        environment.pop("DOCKER_HOST", None)
    return environment


def mount_args(profile: Profile) -> list[str]:
    if profile.target == "local":
        profile.local_workspace.mkdir(parents=True, exist_ok=True)
        source = profile.local_workspace
        mount_type = "bind"
    else:
        source = profile.remote_workspace
        mount_type = profile.remote_workspace_type
    return ["--mount", f"type={mount_type},source={source},target=/app/data"]


def _parsed_env_values(profile: Profile) -> dict[str, str]:
    if profile.env_file is None:
        return {}

    values = dotenv_values(profile.env_file)
    parsed: dict[str, str] = {}
    for key, value in values.items():
        if value is None:
            if key in os.environ:
                parsed[key] = os.environ[key]
            continue
        parsed[key] = value
    return parsed


def _container_env_values(profile: Profile) -> dict[str, str]:
    return {
        key: value
        for key, value in _parsed_env_values(profile).items()
        if key not in DOCKER_CLIENT_ENV_VARS
    }


def _run(
    command: Sequence[str],
    profile: Profile,
    *,
    capture: bool = False,
    check: bool = True,
    stdout: IO[str] | int | None = None,
    stderr: IO[str] | int | None = None,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=REPO_ROOT,
        env=(environment if environment is not None else docker_environment(profile)),
        check=check,
        text=True,
        capture_output=capture,
        stdout=stdout,
        stderr=stderr,
    )


def _docker(
    profile: Profile, *arguments: str, **kwargs: object
) -> subprocess.CompletedProcess[str]:
    return _run(["docker", *arguments], profile, **kwargs)


def require_docker(profile: Profile) -> None:
    try:
        _docker(profile, "info", capture=True)
    except FileNotFoundError as exc:
        raise OperatorError("Docker CLI is not installed or not on PATH") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise OperatorError(
            f"Docker is unavailable for target {profile.target}: {detail}"
        ) from exc


def fly_command(arguments: Sequence[str]) -> int:
    script = REPO_ROOT / "scripts/ingest/fly_ingest.sh"
    return subprocess.run(
        [str(script), *arguments], cwd=REPO_ROOT, check=False
    ).returncode


def _docker_log_path(profile: Profile) -> Path:
    log_dir = REPO_ROOT / "logs" / "deploy"
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return log_dir / f"docker_ingest_logs_{profile.target}_{timestamp}.log"


def build_image(profile: Profile) -> int:
    if profile.target == "fly":
        return fly_command(["deploy"])
    require_docker(profile)
    command = [
        "docker",
        "build",
        "--file",
        "Dockerfile.ingest",
        "--build-arg",
        f"GIT_SHA={_git_sha()}",
        "--build-arg",
        f"BUILD_TIMESTAMP={_build_timestamp()}",
        "--tag",
        profile.image,
        ".",
    ]
    _run(command, profile)
    return 0


def _git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def _build_timestamp() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _container_state(profile: Profile) -> str | None:
    result = _docker(
        profile,
        "inspect",
        "--format",
        "{{.State.Status}}",
        profile.container_name,
        capture=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _run_arguments(mode: str) -> list[str]:
    if mode == "fresh":
        return ["--reset-state"]
    if mode == "resume":
        return []
    try:
        return ["--only-stage", STAGE_OPTIONS[mode]]
    except KeyError as exc:
        raise OperatorError(f"unsupported run mode: {mode}") from exc


def start_run(profile: Profile, mode: str) -> int:
    require_docker(profile)
    existing_state = _container_state(profile)
    if existing_state == "running":
        raise OperatorError(
            f"container {profile.container_name} is already running; "
            "a second collection run is not allowed"
        )
    if existing_state is not None:
        _docker(profile, "rm", profile.container_name)

    run_id = str(uuid.uuid4())
    parsed_env = _container_env_values(profile)
    environment = docker_environment(profile)
    environment.update(parsed_env)
    command = _build_run_command(profile, mode, run_id, parsed_env)
    result = _run(command, profile, capture=True, environment=environment)
    print(f"Started {profile.target} ingest container {result.stdout.strip()}")
    print(f"Container name: {profile.container_name}")
    print(f"Run ID: {run_id}")
    return 0


def _build_run_command(
    profile: Profile,
    mode: str,
    run_id: str,
    env_names: Sequence[str] = (),
) -> list[str]:
    command = [
        "docker",
        "run",
        "--detach",
        "--name",
        profile.container_name,
        "--restart=no",
        "--label",
        f"com.pax-tt.ingest.target={profile.target}",
        "--label",
        f"com.pax-tt.ingest.run-id={run_id}",
        *mount_args(profile),
    ]
    for name in env_names:
        command.extend(["--env", name])
    command.extend(
        [
            "--env",
            f"INGEST_TARGET={profile.target}",
            "--env",
            f"INGEST_RUNTIME_NAME={profile.container_name}",
            "--env",
            f"INGEST_RUN_ID={run_id}",
            "--env",
            f"INGEST_WORKSPACE={profile.workspace_label}",
            profile.image,
            "bash",
            "scripts/ingest/run_container.sh",
            "poetry",
            "run",
            "python",
            "scripts/data_pipeline/run_ingest_pipeline.py",
            *_run_arguments(mode),
        ]
    )
    return command


def _workspace_file(profile: Profile, relative_path: str) -> str:
    command = [
        "docker",
        "run",
        "--rm",
        *mount_args(profile),
        profile.image,
        "sh",
        "-c",
        f"if [ -f '{relative_path}' ]; then cat '{relative_path}'; fi",
    ]
    result = _run(command, profile, capture=True)
    return result.stdout.strip()


def show_status(profile: Profile) -> int:
    if profile.target == "fly":
        return fly_command(["machine", "status"])
    require_docker(profile)
    state = _container_state(profile) or "absent"
    print(f"target={profile.target}")
    print(f"image={profile.image}")
    print(f"workspace={profile.workspace_label}")
    print(f"container={profile.container_name}")
    print(f"container_state={state}")
    owner = _workspace_file(profile, "/app/data/ingest/run_owner.json")
    run_state = _workspace_file(profile, "/app/data/ingest/run_state.json")
    print("run_owner=" + (owner if owner else "absent"))
    print("run_state=" + (run_state if run_state else "absent"))
    return 0


def show_logs(profile: Profile, *, follow: bool) -> int:
    if profile.target == "fly":
        return fly_command(["logs"])
    require_docker(profile)
    arguments = ["logs"]
    if follow:
        arguments.append("--follow")
    arguments.append(profile.container_name)
    log_path = _docker_log_path(profile)
    print(f"Writing Docker logs to {log_path}")
    with log_path.open("w", encoding="utf-8") as log_file:
        result = _docker(
            profile,
            *arguments,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            check=False,
        )
    print(f"Wrote Docker logs to {log_path}")
    return result.returncode


def stop_run(profile: Profile) -> int:
    if profile.target == "fly":
        return fly_command(["maintenance", "stop"])
    require_docker(profile)
    state = _container_state(profile)
    if state == "running":
        _docker(profile, "stop", profile.container_name)
    else:
        print(f"Container {profile.container_name} is not running.")
    return 0


def _artifact_relative_path(remote_path: str):
    try:
        return artifact_relative_path(remote_path)
    except ExportError as exc:
        raise OperatorError(str(exc)) from exc


def _artifact_output_dir(remote_path: str, override: str | None) -> Path:
    try:
        return artifact_output_dir(remote_path, override)
    except ExportError as exc:
        raise OperatorError(str(exc)) from exc


def _container_for_export(profile: Profile) -> tuple[str, bool]:
    if _container_state(profile) == "running":
        return profile.container_name, False
    container_name = f"{profile.container_name}-export-{uuid.uuid4().hex[:8]}"
    result = _docker(
        profile,
        "create",
        "--name",
        container_name,
        *mount_args(profile),
        profile.image,
        "sh",
        "-c",
        "while :; do sleep 3600; done",
        capture=True,
    )
    container = result.stdout.strip()
    _docker(profile, "start", container)
    return container, True


class _DockerArtifactSource:
    def __init__(self, profile: Profile, container: str):
        self.profile = profile
        self.container = container

    def size(self, remote_path: str) -> int:
        result = _docker(
            self.profile,
            "exec",
            self.container,
            "stat",
            "-c",
            "%s",
            remote_path,
            capture=True,
        )
        value = result.stdout.strip()
        if not value.isdigit():
            raise OperatorError(
                f"could not determine remote file size for {remote_path}"
            )
        return int(value)

    def sha256(self, remote_path: str) -> str:
        result = _docker(
            self.profile,
            "exec",
            self.container,
            "sha256sum",
            remote_path,
            capture=True,
        )
        value = result.stdout.strip().split()
        if not value:
            raise OperatorError(f"failed to compute remote SHA-256 for {remote_path}")
        return value[0]

    def read_chunk(
        self,
        remote_path: str,
        chunk_index: int,
        chunk_mb: int,
        expected_size: int,
        output_path: Path,
    ) -> None:
        count_mb = (expected_size + MEGABYTE - 1) // MEGABYTE
        command = [
            "docker",
            "exec",
            self.container,
            "dd",
            f"if={remote_path}",
            "bs=1M",
            f"skip={chunk_index * chunk_mb}",
            f"count={count_mb}",
            "status=none",
        ]
        try:
            with output_path.open("wb") as output:
                result = subprocess.run(
                    command,
                    cwd=REPO_ROOT,
                    env=docker_environment(self.profile),
                    stdout=output,
                    stderr=subprocess.PIPE,
                    check=False,
                )
        except FileNotFoundError as exc:
            raise OperatorError("Docker CLI is not installed or not on PATH") from exc
        if result.returncode != 0:
            detail = result.stderr.decode(errors="replace").strip()
            raise OperatorError(f"Docker chunk download failed: {detail}")


def export_artifact(
    profile: Profile,
    remote_path: str,
    output_dir: str | None,
    overwrite: bool,
    chunk_mb: int,
    keep_parts: bool,
) -> int:
    if profile.target == "fly":
        arguments = [
            "artifacts",
            "download",
            "--remote-path",
            remote_path,
            "--chunk-mb",
            str(chunk_mb),
        ]
        if output_dir is not None:
            arguments.extend(["--output-dir", output_dir])
        if overwrite:
            arguments.append("--overwrite")
        if keep_parts:
            arguments.append("--keep-parts")
        return fly_command(arguments)
    require_docker(profile)
    relative_path = _artifact_relative_path(remote_path)
    destination_dir = _artifact_output_dir(remote_path, output_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / relative_path.name
    if destination.exists() and not overwrite:
        source = profile.local_workspace / relative_path
        if profile.target == "local" and source.resolve() == destination.resolve():
            print(f"Artifact already present at {destination}")
            return 0
        raise OperatorError(
            f"refusing to overwrite existing artifact {destination}; use --overwrite"
        )

    container, temporary = _container_for_export(profile)
    try:
        source = _DockerArtifactSource(profile, container)
        try:
            export_verified_artifact(
                source,
                remote_path,
                destination_dir,
                chunk_mb=chunk_mb,
                keep_parts=keep_parts,
                overwrite=overwrite,
            )
        except (ExportError, OSError) as exc:
            raise OperatorError(str(exc)) from exc
    finally:
        if temporary:
            _docker(profile, "rm", "--force", container, check=False)
    return 0


def list_artifacts(profile: Profile) -> int:
    if profile.target == "fly":
        return fly_command(["artifacts", "list"])
    require_docker(profile)
    command = [
        "docker",
        "run",
        "--rm",
        *mount_args(profile),
        profile.image,
        "sh",
        "-c",
        "if [ -d /app/data/ingest ]; then "
        "find /app/data/ingest -maxdepth 2 -type f "
        "\\( -name 'boardgame_ranks_*' -o -name 'boardgame_data_*' "
        "-o -name 'boardgame_ratings_*' \\) -print; "
        "fi",
    ]
    return _run(command, profile).returncode


def unlock_workspace(profile: Profile, force: bool) -> int:
    if not force:
        raise OperatorError("unlock requires --force after checking status")
    if profile.target == "fly":
        raise OperatorError("workspace unlock is not available through the Fly adapter")
    require_docker(profile)
    command = [
        "docker",
        "run",
        "--rm",
        *mount_args(profile),
        profile.image,
        "poetry",
        "run",
        "python",
        "scripts/ingest/runtime_lock.py",
        "clear",
        "--force",
    ]
    _run(command, profile)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("local", "remote", "fly"))
    parser.add_argument("--image")
    parser.add_argument("--container-name")
    parser.add_argument("--local-workspace")
    parser.add_argument("--env-file")
    parser.add_argument("--remote-host")
    parser.add_argument("--remote-workspace")
    parser.add_argument("--remote-workspace-type", choices=("volume", "bind"))
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("build")
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument(
        "mode", choices=("ranks", "game-data", "ratings", "fresh", "resume")
    )
    subparsers.add_parser("status")
    logs_parser = subparsers.add_parser("logs")
    logs_parser.add_argument("--follow", action="store_true")
    subparsers.add_parser("stop")
    subparsers.add_parser("list")
    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("--remote-path", required=True)
    export_parser.add_argument("--output-dir")
    export_parser.add_argument("--chunk-mb", type=int, default=64)
    export_parser.add_argument("--keep-parts", action="store_true")
    export_parser.add_argument("--overwrite", action="store_true")
    unlock_parser = subparsers.add_parser("unlock")
    unlock_parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        profile = build_profile(args)
        if args.command == "build":
            return build_image(profile)
        if args.command == "run":
            if profile.target == "fly":
                return fly_command(["run", args.mode])
            return start_run(profile, args.mode)
        if args.command == "status":
            return show_status(profile)
        if args.command == "logs":
            return show_logs(profile, follow=args.follow)
        if args.command == "stop":
            return stop_run(profile)
        if args.command == "list":
            return list_artifacts(profile)
        if args.command == "export":
            return export_artifact(
                profile,
                args.remote_path,
                args.output_dir,
                args.overwrite,
                args.chunk_mb,
                args.keep_parts,
            )
        if args.command == "unlock":
            return unlock_workspace(profile, args.force)
    except (OperatorError, subprocess.CalledProcessError) as exc:
        if isinstance(exc, subprocess.CalledProcessError):
            detail = (exc.stderr or exc.stdout or "").strip()
            print(f"Error: command failed: {detail}", file=sys.stderr)
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
