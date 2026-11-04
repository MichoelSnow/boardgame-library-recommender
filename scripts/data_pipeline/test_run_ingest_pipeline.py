import json
import os
from datetime import UTC, datetime

import pytest

from scripts.data_pipeline import run_ingest_pipeline


def test_build_initial_state_excludes_ratings_when_skipped():
    state = run_ingest_pipeline._build_initial_state(include_ratings=False)

    assert "get_ranks" in state["stages"]
    assert "get_game_data" in state["stages"]
    assert "get_ratings" not in state["stages"]


def test_next_incomplete_stage_returns_first_pending():
    stages = run_ingest_pipeline._selected_stages(include_ratings=True)
    state = run_ingest_pipeline._build_initial_state(include_ratings=True)
    state["stages"]["get_ranks"]["status"] = "completed"

    next_stage = run_ingest_pipeline._next_incomplete_stage(state, stages)

    assert next_stage is not None
    assert next_stage.name == "get_game_data"


def test_new_run_fetches_fresh_game_data():
    stages = run_ingest_pipeline._selected_stages(
        include_ratings=True, continue_game_data=False
    )

    game_data_stage = next(stage for stage in stages if stage.name == "get_game_data")

    assert "--continue-from-last" not in game_data_stage.command


def test_retry_continues_game_data():
    stages = run_ingest_pipeline._selected_stages(
        include_ratings=True, continue_game_data=True
    )

    game_data_stage = next(stage for stage in stages if stage.name == "get_game_data")

    assert "--continue-from-last" in game_data_stage.command


def test_only_stage_selects_ratings():
    stages = run_ingest_pipeline._selected_stages(
        include_ratings=True, only_stage="get_ratings"
    )

    assert [stage.name for stage in stages] == ["get_ratings"]


def test_stage_prerequisites():
    state = run_ingest_pipeline._build_initial_state(include_ratings=True)

    with pytest.raises(ValueError, match="requires get_ranks"):
        run_ingest_pipeline._validate_stage_prerequisite(
            state, stage_name="get_game_data"
        )

    state["stages"]["get_ranks"]["status"] = "completed"
    run_ingest_pipeline._validate_stage_prerequisite(state, stage_name="get_game_data")


def test_only_stage_updates_only_requested_stage(tmp_path, monkeypatch):
    state_path = tmp_path / "run_state.json"
    state = run_ingest_pipeline._build_initial_state(include_ratings=True)
    state["stages"]["get_ranks"]["status"] = "completed"
    run_ingest_pipeline._save_state(state_path, state)

    monkeypatch.setattr(
        run_ingest_pipeline,
        "_run_stage",
        lambda stage: 0,
    )
    monkeypatch.setattr(run_ingest_pipeline, "_notify", lambda *args, **kwargs: None)
    monkeypatch.setenv("INGEST_MAINTENANCE_MODE", "false")
    monkeypatch.setattr(
        run_ingest_pipeline.sys,
        "argv",
        [
            "run_ingest_pipeline.py",
            "--state-path",
            str(state_path),
            "--log-dir",
            str(tmp_path / "logs"),
            "--only-stage",
            "get_ranks",
        ],
    )

    assert run_ingest_pipeline.main() == 0

    refreshed = run_ingest_pipeline._load_state(state_path)
    assert refreshed["stages"]["get_ranks"]["status"] == "completed"
    assert refreshed["stages"]["get_game_data"]["status"] == "pending"
    assert refreshed["stages"]["get_ratings"]["status"] == "pending"
    assert refreshed["status"] == "running"


def test_save_and_load_state_round_trip(tmp_path):
    state_path = tmp_path / "run_state.json"
    initial = run_ingest_pipeline._build_initial_state(include_ratings=True)
    run_ingest_pipeline._save_state(state_path, initial)

    loaded = run_ingest_pipeline._load_state(state_path)

    assert loaded["schema_version"] == 1
    assert loaded["status"] == "running"
    assert set(loaded["stages"].keys()) == {"get_ranks", "get_game_data", "get_ratings"}
    json.dumps(loaded)


def test_completed_state_starts_a_new_run():
    state = {"status": "completed"}

    assert run_ingest_pipeline._should_start_new_run(state, reset_state=False)


def test_incomplete_state_resumes_by_default():
    state = {"status": "failed"}

    assert not run_ingest_pipeline._should_start_new_run(state, reset_state=False)


def test_reset_state_starts_a_new_run():
    state = {"status": "running"}

    assert run_ingest_pipeline._should_start_new_run(state, reset_state=True)


def test_maintenance_deadline_parses_utc_timestamp(monkeypatch):
    monkeypatch.setenv("INGEST_MAINTENANCE_UNTIL_UTC", "2026-11-03T18:00:00Z")

    assert run_ingest_pipeline._maintenance_deadline() == datetime(
        2026, 11, 3, 18, tzinfo=UTC
    )


def test_maintenance_deadline_requires_a_timezone(monkeypatch):
    monkeypatch.setenv("INGEST_MAINTENANCE_UNTIL_UTC", "2026-11-03T18:00:00")

    with pytest.raises(ValueError, match="must include a timezone"):
        run_ingest_pipeline._maintenance_deadline()


def test_maintenance_mode_refuses_to_run_without_a_lease(monkeypatch):
    monkeypatch.setenv("INGEST_MAINTENANCE_MODE", "true")
    monkeypatch.delenv("INGEST_MAINTENANCE_UNTIL_UTC", raising=False)

    assert run_ingest_pipeline._enter_maintenance_mode() == 1


def test_cleanup_superseded_ingest_artifacts_keeps_latest_files(tmp_path):
    game_data_dir = tmp_path / "game_data"
    ranks_dir = tmp_path / "ranks"
    game_data_dir.mkdir()
    ranks_dir.mkdir()
    old_file = game_data_dir / "boardgame_data_1.duckdb"
    latest_file = game_data_dir / "boardgame_data_2.duckdb"
    old_wal = game_data_dir / "boardgame_data_1.duckdb.wal"
    old_ranks = ranks_dir / "boardgame_ranks_1.csv"
    latest_ranks = ranks_dir / "boardgame_ranks_2.csv"
    old_file.write_bytes(b"old")
    latest_file.write_bytes(b"latest")
    old_wal.write_bytes(b"old wal")
    old_ranks.write_bytes(b"old ranks")
    latest_ranks.write_bytes(b"latest ranks")
    old_file.touch()
    latest_file.touch()
    old_ranks.touch()
    latest_ranks.touch()
    for path in (old_file, old_wal, old_ranks):
        os.utime(path, (1, 1))
    for path in (latest_file, latest_ranks):
        os.utime(path, (2, 2))

    removed = run_ingest_pipeline._cleanup_superseded_ingest_artifacts(tmp_path)

    assert set(removed) == {old_file, old_wal, old_ranks}
    assert not old_file.exists()
    assert latest_file.exists()
    assert not old_ranks.exists()
    assert latest_ranks.exists()


def test_notify_and_reset_max_attempt_stage_resets_attempt_counter(
    tmp_path, monkeypatch
):
    state_path = tmp_path / "run_state.json"
    state = run_ingest_pipeline._build_initial_state(include_ratings=True)
    state["stages"]["get_game_data"]["attempts"] = 3
    state["stages"]["get_game_data"]["status"] = "failed"
    run_ingest_pipeline._save_state(state_path, state)

    monkeypatch.setattr(
        "scripts.data_pipeline.run_ingest_pipeline._notify",
        lambda *args, **kwargs: None,
    )

    exit_code = run_ingest_pipeline._notify_and_reset_max_attempt_stage(
        state=state,
        state_path=state_path,
        stage_name="get_game_data",
        reason="max_attempts_reached_post_failure (limit=3)",
    )

    refreshed = run_ingest_pipeline._load_state(state_path)
    assert exit_code == 1
    assert refreshed["stages"]["get_game_data"]["attempts"] == 0
    assert refreshed["stages"]["get_game_data"]["status"] == "failed"
    assert refreshed["stages"]["get_game_data"]["last_error"].startswith(
        "max_attempts_reached"
    )
