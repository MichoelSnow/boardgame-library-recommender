import sqlalchemy as sa
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine

from backend.scripts.migrate_sqlite_to_postgres import (
    fetch_source_rows,
    get_table_copy_order,
    migrate_table,
    normalize_row_for_target,
    reset_postgres_sequences,
)


def test_get_table_copy_order_matches_expected_dependency_sequence():
    assert get_table_copy_order() == [
        "games",
        "users",
        "artists",
        "categories",
        "compilations",
        "designers",
        "expansions",
        "families",
        "implementations",
        "integrations",
        "language_dependence",
        "library_games",
        "mechanics",
        "publishers",
        "suggested_players",
        "user_suggestions",
        "versions",
    ]


def test_fetch_source_rows_yields_rows_without_materializing_helper_output():
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    table = Table(
        "sample_rows",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String, nullable=False),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            table.insert(),
            [
                {"id": 1, "name": "one"},
                {"id": 2, "name": "two"},
                {"id": 3, "name": "three"},
            ],
        )

    with engine.connect() as connection:
        rows = list(fetch_source_rows(connection, table))

    assert rows == [
        {"id": 1, "name": "one"},
        {"id": 2, "name": "two"},
        {"id": 3, "name": "three"},
    ]


def test_normalize_row_for_target_converts_legacy_zero_bgg_id_to_null():
    row = {"id": 1, "bgg_id": 0, "name": "Example"}
    anomaly_counts: dict[str, int] = {}

    result = normalize_row_for_target(
        "library_games", row, anomaly_counts=anomaly_counts
    )

    assert result["bgg_id"] is None
    assert row["bgg_id"] == 0
    assert anomaly_counts == {"library_games_zero_bgg_id": 1}


def test_normalize_row_for_target_leaves_other_rows_unchanged():
    row = {"id": 2, "bgg_id": 123, "name": "Example"}

    result = normalize_row_for_target("library_games", row)

    assert result == row


def test_normalize_row_for_target_nulls_orphaned_library_game_reference():
    row = {"id": 3, "bgg_id": 63993, "name": "Example"}
    anomaly_counts: dict[str, int] = {}

    result = normalize_row_for_target(
        "library_games",
        row,
        valid_game_ids={1, 2, 3},
        anomaly_counts=anomaly_counts,
    )

    assert result["bgg_id"] is None
    assert row["bgg_id"] == 63993
    assert anomaly_counts == {"library_games_orphan_bgg_id": 1}


def test_migrate_table_streams_rows_in_batches():
    source_engine = create_engine("sqlite:///:memory:")
    target_engine = create_engine("sqlite:///:memory:")

    source_metadata = MetaData()
    target_metadata = MetaData()

    source_table = Table(
        "sample_rows",
        source_metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String, nullable=False),
    )
    target_table = Table(
        "sample_rows",
        target_metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String, nullable=False),
    )

    source_metadata.create_all(source_engine)
    target_metadata.create_all(target_engine)

    with source_engine.begin() as connection:
        connection.execute(
            source_table.insert(),
            [
                {"id": 1, "name": "one"},
                {"id": 2, "name": "two"},
                {"id": 3, "name": "three"},
                {"id": 4, "name": "four"},
                {"id": 5, "name": "five"},
            ],
        )

    with (
        source_engine.connect() as source_connection,
        target_engine.begin() as target_connection,
    ):
        source_count, target_count = migrate_table(
            table_name="sample_rows",
            source_connection=source_connection,
            target_connection=target_connection,
            source_table=source_table,
            target_table=target_table,
            batch_size=2,
        )

    assert source_count == 5
    assert target_count == 5

    with target_engine.connect() as connection:
        rows = connection.execute(
            sa.select(target_table.c.id, target_table.c.name).order_by(
                target_table.c.id
            )
        ).fetchall()

    assert rows == [
        (1, "one"),
        (2, "two"),
        (3, "three"),
        (4, "four"),
        (5, "five"),
    ]


def test_reset_postgres_sequences_only_targets_integer_primary_keys():
    metadata = MetaData()
    with_id = Table(
        "with_id",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String),
    )
    without_integer_id = Table(
        "without_integer_id",
        metadata,
        Column("slug", String, primary_key=True),
    )

    executed = []

    class FakeConnection:
        def execute(self, statement):
            executed.append(str(statement))

    reset_postgres_sequences(
        ["with_id", "without_integer_id"],
        FakeConnection(),
        {
            "with_id": with_id,
            "without_integer_id": without_integer_id,
        },
    )

    assert len(executed) == 1
    assert "with_id" in executed[0]
