from backend.scripts.migrate_sqlite_to_postgres import (
    get_table_copy_order,
    iter_batches,
    normalize_row_for_target,
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
        "mechanics",
        "pax_games",
        "publishers",
        "suggested_players",
        "user_suggestions",
        "versions",
    ]


def test_iter_batches_splits_rows_into_stable_chunks():
    rows = [{"id": index} for index in range(5)]

    result = list(iter_batches(rows, batch_size=2))

    assert result == [
        [{"id": 0}, {"id": 1}],
        [{"id": 2}, {"id": 3}],
        [{"id": 4}],
    ]


def test_normalize_row_for_target_converts_legacy_zero_bgg_id_to_null():
    row = {"id": 1, "bgg_id": 0, "name": "Example"}

    result = normalize_row_for_target("pax_games", row)

    assert result["bgg_id"] is None
    assert row["bgg_id"] == 0


def test_normalize_row_for_target_leaves_other_rows_unchanged():
    row = {"id": 2, "bgg_id": 123, "name": "Example"}

    result = normalize_row_for_target("pax_games", row)

    assert result == row


def test_normalize_row_for_target_nulls_orphaned_pax_game_reference():
    row = {"id": 3, "bgg_id": 63993, "name": "Example"}

    result = normalize_row_for_target("pax_games", row, valid_game_ids={1, 2, 3})

    assert result["bgg_id"] is None
    assert row["bgg_id"] == 63993
