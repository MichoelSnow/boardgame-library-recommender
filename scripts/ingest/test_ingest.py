import subprocess
from argparse import Namespace
from pathlib import Path

import pytest

from scripts.ingest import ingest
from scripts.ingest import runtime_lock


def test_remote_profile_requires_docker_host(monkeypatch):
    monkeypatch.delenv("INGEST_REMOTE_DOCKER_HOST", raising=False)

    with pytest.raises(ingest.OperatorError, match="remote target requires"):
        ingest.build_profile(
            Namespace(
                target="remote",
                image=None,
                container_name=None,
                local_workspace=None,
                remote_host=None,
                remote_workspace=None,
                remote_workspace_type=None,
                env_file=None,
            )
        )


def test_remote_bind_mount_preserves_remote_source(monkeypatch):
    monkeypatch.delenv("INGEST_ENV_FILE", raising=False)
    profile = ingest.build_profile(
        Namespace(
            target="remote",
            image=None,
            container_name=None,
            local_workspace=None,
            remote_host="ssh://msnow@example.invalid",
            remote_workspace="/srv/bg-lib-ingest",
            remote_workspace_type="bind",
            env_file=None,
        )
    )

    assert ingest.mount_args(profile) == [
        "--mount",
        "type=bind,source=/srv/bg-lib-ingest,target=/app/data",
    ]
    assert str(Path.cwd()) not in ingest.mount_args(profile)[1]


def test_remote_run_command_uses_target_and_remote_mount(monkeypatch):
    monkeypatch.delenv("INGEST_ENV_FILE", raising=False)
    profile = ingest.build_profile(
        Namespace(
            target="remote",
            image="example/ingest:test",
            container_name="remote-ingest",
            local_workspace=None,
            remote_host="ssh://msnow@example.invalid",
            remote_workspace="bg-lib-ingest-data",
            remote_workspace_type="volume",
            env_file=None,
        )
    )

    command = ingest._build_run_command(profile, "fresh", "run-123")

    assert "--detach" in command
    assert "--env" in command
    assert "INGEST_TARGET=remote" in command
    assert "INGEST_RUN_ID=run-123" in command
    assert "--mount" in command
    assert "type=volume,source=bg-lib-ingest-data,target=/app/data" in command
    assert command[-1] == "--reset-state"


def test_docker_environment_parses_dotenv_quotes_without_exposing_values(tmp_path):
    source_env = tmp_path / ".env"
    source_env.write_text(
        'BGG_TOKEN="quoted-token"\n'
        "BGG_RANKS_ZIP_URL='https://example.test/ranks.zip?sig=a&b=c'\n"
        "DOCKER_HOST=should-not-override\n",
        encoding="utf-8",
    )
    profile = ingest.Profile(
        target="local",
        image="example/ingest:test",
        container_name="local-ingest",
        local_workspace=tmp_path / "workspace",
        remote_host=None,
        remote_workspace="bg-lib-ingest-data",
        remote_workspace_type="volume",
        env_file=source_env,
    )

    parsed = ingest._parsed_env_values(profile)
    container_values = ingest._container_env_values(profile)
    command = ingest._build_run_command(profile, "fresh", "run-123", container_values)

    assert parsed == {
        "BGG_TOKEN": "quoted-token",
        "BGG_RANKS_ZIP_URL": "https://example.test/ranks.zip?sig=a&b=c",
        "DOCKER_HOST": "should-not-override",
    }
    assert "DOCKER_HOST" not in container_values
    assert container_values["BGG_TOKEN"] == "quoted-token"
    assert "BGG_TOKEN" in command
    assert "BGG_RANKS_ZIP_URL" in command
    assert "quoted-token" not in command
    assert str(source_env) not in command


def test_start_run_passes_parsed_dotenv_values_to_docker_environment(
    tmp_path, monkeypatch
):
    source_env = tmp_path / ".env"
    source_env.write_text('BGG_TOKEN="quoted-token"\n', encoding="utf-8")
    profile = ingest.Profile(
        target="local",
        image="example/ingest:test",
        container_name="local-ingest",
        local_workspace=tmp_path / "workspace",
        remote_host=None,
        remote_workspace="bg-lib-ingest-data",
        remote_workspace_type="volume",
        env_file=source_env,
    )
    calls = []

    monkeypatch.setattr(ingest, "require_docker", lambda _profile: None)
    monkeypatch.setattr(ingest, "_container_state", lambda _profile: None)

    def fake_run(command, _profile, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="container-id\n")

    monkeypatch.setattr(ingest, "_run", fake_run)

    assert ingest.start_run(profile, "fresh") == 0
    command, kwargs = calls[0]
    assert "--env-file" not in command
    assert command[command.index("--env") + 1] == "BGG_TOKEN"
    assert kwargs["environment"]["BGG_TOKEN"] == "quoted-token"


def test_docker_logs_are_written_to_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ingest, "REPO_ROOT", tmp_path)
    profile = ingest.Profile(
        target="remote",
        image="example/ingest:test",
        container_name="remote-ingest",
        local_workspace=tmp_path / "local",
        remote_host="ssh://msnow@example.invalid",
        remote_workspace="bg-lib-ingest-data",
        remote_workspace_type="volume",
        env_file=None,
    )

    monkeypatch.setattr(ingest, "require_docker", lambda _profile: None)

    def fake_docker(_profile, *arguments, **kwargs):
        assert arguments == ("logs", "remote-ingest")
        assert kwargs["check"] is False
        kwargs["stdout"].write("application log line\n")
        return subprocess.CompletedProcess(
            ["docker", *arguments],
            0,
        )

    monkeypatch.setattr(ingest, "_docker", fake_docker)

    assert ingest.show_logs(profile, follow=False) == 0

    output = capsys.readouterr().out
    assert "application log line" not in output
    log_files = list(
        (tmp_path / "logs" / "deploy").glob("docker_ingest_logs_remote_*.log")
    )
    assert len(log_files) == 1
    assert log_files[0].read_text(encoding="utf-8") == "application log line\n"


def test_artifact_path_rejects_paths_outside_ingest():
    with pytest.raises(ingest.OperatorError):
        ingest._artifact_relative_path("/app/data/other/file.duckdb")


def test_lock_rejects_second_owner(tmp_path, monkeypatch):
    lock_path = tmp_path / "run_owner.json"
    monkeypatch.setenv("INGEST_RUN_ID", "first")
    runtime_lock.acquire(lock_path)

    monkeypatch.setenv("INGEST_RUN_ID", "second")
    with pytest.raises(RuntimeError, match="already owned"):
        runtime_lock.acquire(lock_path)


def test_lock_release_requires_owner(tmp_path, monkeypatch):
    lock_path = tmp_path / "run_owner.json"
    monkeypatch.setenv("INGEST_RUN_ID", "first")
    runtime_lock.acquire(lock_path)

    monkeypatch.setenv("INGEST_RUN_ID", "second")
    with pytest.raises(RuntimeError, match="belongs to run"):
        runtime_lock.release(lock_path)
