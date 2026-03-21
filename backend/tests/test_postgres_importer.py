import pandas as pd

from backend.app.importers.postgres_importer import (
    GAME_SOURCE_TO_TARGET,
    RELATION_SPECS,
    _prepare_games_dataframe,
    _prepare_relation_dataframe,
)


def _relation_spec(entity: str) -> dict:
    for spec in RELATION_SPECS:
        if spec["entity"] == entity:
            return spec
    raise AssertionError(f"missing spec for {entity}")


def test_prepare_games_dataframe_renames_and_dedupes_ids():
    frame = pd.DataFrame(
        [
            {"id": 1, "name": "A", "minplayers": 1, "maxplayers": 4},
            {"id": 1, "name": "A-dup", "minplayers": 1, "maxplayers": 4},
            {"id": 2, "name": "B", "minplayers": 2, "maxplayers": 5},
        ]
    )

    prepared = _prepare_games_dataframe(frame)

    assert list(prepared.columns) == list(GAME_SOURCE_TO_TARGET.values())
    assert prepared["id"].tolist() == [1, 2]
    assert prepared["min_players"].tolist() == [1, 2]
    assert prepared["max_players"].tolist() == [4, 5]


def test_prepare_relation_dataframe_dedupes_designer_names_per_game():
    spec = _relation_spec("boardgamedesigner")
    frame = pd.DataFrame(
        [
            {
                "game_id": 2853,
                "boardgamedesigner_id": 1156,
                "boardgamedesigner_name": "Fritz Bronner",
            },
            {
                "game_id": 2853,
                "boardgamedesigner_id": 155388,
                "boardgamedesigner_name": "Fritz Bronner",
            },
            {
                "game_id": 2853,
                "boardgamedesigner_id": 760,
                "boardgamedesigner_name": "John Olsen",
            },
        ]
    )

    prepared = _prepare_relation_dataframe(spec, frame)

    assert prepared["boardgamedesigner_name"].tolist() == [
        "Fritz Bronner",
        "John Olsen",
    ]


def test_prepare_relation_dataframe_renames_language_dependence_columns():
    spec = _relation_spec("language_dependence")
    frame = pd.DataFrame(
        [
            {
                "id": 10,
                "1": 1,
                "2": 2,
                "3": 3,
                "4": 4,
                "5": 5,
                "total_votes": 22,
                "language_dependency": 3,
            }
        ]
    )

    prepared = _prepare_relation_dataframe(spec, frame)

    assert prepared.loc[0, "game_id"] == 10
    assert prepared.loc[0, "level_1"] == 1
    assert prepared.loc[0, "level_5"] == 5
