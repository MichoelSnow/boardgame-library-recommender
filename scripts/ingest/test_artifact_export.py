import hashlib

import pytest

from scripts.ingest.artifact_export import ExportError, export_verified_artifact


class FakeArtifactSource:
    def __init__(self, data: bytes, *, reported_sha: str | None = None):
        self.data = data
        self.reported_sha = reported_sha
        self.read_indices: list[int] = []

    def size(self, remote_path: str) -> int:
        return len(self.data)

    def sha256(self, remote_path: str) -> str:
        return self.reported_sha or hashlib.sha256(self.data).hexdigest()

    def read_chunk(
        self,
        remote_path: str,
        chunk_index: int,
        chunk_mb: int,
        expected_size: int,
        output_path,
    ) -> None:
        self.read_indices.append(chunk_index)
        chunk_bytes = chunk_mb * 1024 * 1024
        start = chunk_index * chunk_bytes
        output_path.write_bytes(self.data[start : start + expected_size])


def test_export_verifies_and_cleans_successful_transfer(tmp_path):
    source = FakeArtifactSource(b"a" * (1024 * 1024 + 17))
    output_dir = tmp_path / "data" / "ingest" / "ranks"

    destination = export_verified_artifact(
        source,
        "/app/data/ingest/ranks/boardgame_ranks_test.csv",
        output_dir,
        chunk_mb=1,
    )

    assert destination.read_bytes() == source.data
    assert not (output_dir / ".boardgame_ranks_test.csv.parts").exists()
    assert source.read_indices == [0, 1]


def test_export_resumes_valid_parts_and_keeps_partial_state_on_checksum_failure(
    tmp_path,
):
    data = b"b" * (1024 * 1024 + 17)
    source = FakeArtifactSource(data, reported_sha="0" * 64)
    output_dir = tmp_path / "data" / "ingest" / "game_data"
    parts_dir = output_dir / ".boardgame_data_test.duckdb.parts"
    parts_dir.mkdir(parents=True)
    (parts_dir / "part_000000.bin").write_bytes(data[: 1024 * 1024])

    with pytest.raises(ExportError, match="SHA-256 mismatch"):
        export_verified_artifact(
            source,
            "/app/data/ingest/game_data/boardgame_data_test.duckdb",
            output_dir,
            chunk_mb=1,
        )

    assert source.read_indices == [1]
    assert not (output_dir / "boardgame_data_test.duckdb").exists()
    assert (parts_dir / "part_000000.bin").exists()
    assert (parts_dir / "part_000001.bin").exists()


def test_export_refuses_unrelated_existing_destination(tmp_path):
    output_dir = tmp_path / "data" / "ingest" / "ratings"
    output_dir.mkdir(parents=True)
    destination = output_dir / "boardgame_ratings_test.duckdb"
    destination.write_bytes(b"existing")

    with pytest.raises(ExportError, match="refusing to overwrite"):
        export_verified_artifact(
            FakeArtifactSource(b"new"),
            "/app/data/ingest/ratings/boardgame_ratings_test.duckdb",
            output_dir,
        )

    assert destination.read_bytes() == b"existing"
