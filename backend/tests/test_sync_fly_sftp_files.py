import importlib.util
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "deploy"
    / "sync_fly_sftp_files.py"
)
SPEC = importlib.util.spec_from_file_location("sync_fly_sftp_files", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

build_sync_plan = MODULE.build_sync_plan
load_state = MODULE.load_state
parse_remote_manifest = MODULE.parse_remote_manifest
retain_relevant_completed = MODULE.retain_relevant_completed
save_state = MODULE.save_state


def test_parse_remote_manifest_ignores_invalid_lines():
    raw = "\n".join(
        [
            "alpha.jpg|100",
            "badline",
            "beta.jpg|abc",
            "nested/gamma.jpg|300",
            "",
        ]
    )
    parsed = parse_remote_manifest(raw)
    assert parsed == {"alpha.jpg": 100, "nested/gamma.jpg": 300}


def test_build_sync_plan_only_includes_missing_or_mismatched_sizes(tmp_path: Path):
    local_dir = tmp_path / "images"
    local_dir.mkdir()
    (local_dir / "a.jpg").write_bytes(b"a" * 10)
    (local_dir / "b.jpg").write_bytes(b"b" * 20)
    (local_dir / "c.jpg").write_bytes(b"c" * 30)

    local_manifest = {"a.jpg": 10, "b.jpg": 20, "c.jpg": 30}
    remote_manifest = {"a.jpg": 10, "b.jpg": 99}

    plan = build_sync_plan(local_manifest, remote_manifest, local_dir, "/data/images")
    assert [item.relative_path for item in plan] == ["b.jpg", "c.jpg"]
    assert [item.remote_size for item in plan] == [99, None]
    assert all(item.remote_path.startswith("/data/images/") for item in plan)


def test_state_round_trip(tmp_path: Path):
    state_file = tmp_path / "sync_state.json"
    save_state(state_file, {"b.jpg", "a.jpg"})
    loaded = load_state(state_file)
    assert loaded == {"a.jpg", "b.jpg"}


def test_retain_relevant_completed_prunes_non_pending_entries(tmp_path: Path):
    local_dir = tmp_path / "images"
    local_dir.mkdir()
    (local_dir / "a.jpg").write_bytes(b"a" * 10)
    (local_dir / "b.jpg").write_bytes(b"b" * 20)

    local_manifest = {"a.jpg": 10, "b.jpg": 20}
    remote_manifest = {}
    plan = build_sync_plan(local_manifest, remote_manifest, local_dir, "/data/images")

    completed = {"a.jpg", "stale.jpg"}
    relevant = retain_relevant_completed(completed, plan)

    assert relevant == {"a.jpg"}
