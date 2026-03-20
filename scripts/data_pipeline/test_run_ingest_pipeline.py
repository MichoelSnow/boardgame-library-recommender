import json

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


def test_save_and_load_state_round_trip(tmp_path):
    state_path = tmp_path / "run_state.json"
    initial = run_ingest_pipeline._build_initial_state(include_ratings=True)
    run_ingest_pipeline._save_state(state_path, initial)

    loaded = run_ingest_pipeline._load_state(state_path)

    assert loaded["schema_version"] == 1
    assert loaded["status"] == "running"
    assert set(loaded["stages"].keys()) == {"get_ranks", "get_game_data", "get_ratings"}
    json.dumps(loaded)


def test_stage_can_be_marked_complete_without_run_for_existing_ranks(monkeypatch):
    get_ranks_stage = run_ingest_pipeline.Stage(name="get_ranks", command=["dummy"])

    monkeypatch.setattr(
        "scripts.data_pipeline.run_ingest_pipeline.Path.glob",
        lambda _self, _pattern: [object()],
    )

    assert run_ingest_pipeline._stage_can_be_marked_complete_without_run(
        get_ranks_stage
    )


def test_stage_cannot_be_marked_complete_without_run_for_non_ranks():
    get_game_data_stage = run_ingest_pipeline.Stage(
        name="get_game_data", command=["dummy"]
    )

    assert not run_ingest_pipeline._stage_can_be_marked_complete_without_run(
        get_game_data_stage
    )


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
    assert refreshed["stages"]["get_game_data"]["status"] == "pending"
    assert refreshed["stages"]["get_game_data"]["last_error"].startswith(
        "max_attempts_reached"
    )
