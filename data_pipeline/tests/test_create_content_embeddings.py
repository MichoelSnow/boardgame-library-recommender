from __future__ import annotations

from pathlib import Path

import pandas as pd

from data_pipeline.src.features.create_content_embeddings import (
    _load_csv,
    _playtime_bucket,
    _weight_bucket,
    build_content_feature_matrix,
)


def _write_pipe_csv(path: Path, frame: pd.DataFrame) -> None:
    frame.to_csv(path, sep="|", index=False)


def test_bucket_helpers() -> None:
    assert _playtime_bucket(30) == "playtime:<60"
    assert _playtime_bucket(90) == "playtime:60-120"
    assert _playtime_bucket(180) == "playtime:>120"
    assert _playtime_bucket(None) is None

    assert _weight_bucket(1.7) == "weight:beginner"
    assert _weight_bucket(3.0) == "weight:midweight"
    assert _weight_bucket(4.2) == "weight:heavy"
    assert _weight_bucket(None) is None


def test_build_content_feature_matrix_builds_nonempty_matrix(tmp_path: Path) -> None:
    ts = "9999999999"
    processed_dir = tmp_path / ts
    processed_dir.mkdir(parents=True)

    _write_pipe_csv(
        processed_dir / f"processed_games_data_{ts}.csv",
        pd.DataFrame(
            [
                {
                    "id": 1,
                    "playingtime": 45,
                    "averageweight": 2.5,
                },
                {
                    "id": 2,
                    "playingtime": 130,
                    "averageweight": 3.8,
                },
            ]
        ),
    )

    _write_pipe_csv(
        processed_dir / f"processed_games_boardgamemechanic_{ts}.csv",
        pd.DataFrame(
            [
                {"game_id": 1, "boardgamemechanic_id": 10},
                {"game_id": 2, "boardgamemechanic_id": 20},
            ]
        ),
    )
    _write_pipe_csv(
        processed_dir / f"processed_games_boardgamecategory_{ts}.csv",
        pd.DataFrame(
            [
                {"game_id": 1, "boardgamecategory_id": 100},
                {"game_id": 2, "boardgamecategory_id": 200},
            ]
        ),
    )
    _write_pipe_csv(
        processed_dir / f"processed_games_boardgamefamily_{ts}.csv",
        pd.DataFrame(
            [
                {"game_id": 1, "boardgamefamily_id": 1000},
                {"game_id": 2, "boardgamefamily_id": 2000},
            ]
        ),
    )
    _write_pipe_csv(
        processed_dir / f"processed_games_boardgamedesigner_{ts}.csv",
        pd.DataFrame(
            [
                {"game_id": 1, "boardgamedesigner_id": 11},
                {"game_id": 2, "boardgamedesigner_id": 22},
            ]
        ),
    )
    _write_pipe_csv(
        processed_dir / f"processed_games_boardgameartist_{ts}.csv",
        pd.DataFrame(
            [
                {"game_id": 1, "boardgameartist_id": 111},
                {"game_id": 2, "boardgameartist_id": 222},
            ]
        ),
    )
    _write_pipe_csv(
        processed_dir / f"processed_games_boardgamepublisher_{ts}.csv",
        pd.DataFrame(
            [
                {"game_id": 1, "boardgamepublisher_id": 1111},
                {"game_id": 2, "boardgamepublisher_id": 2222},
            ]
        ),
    )
    _write_pipe_csv(
        processed_dir / f"processed_games_suggested_num_players_{ts}.csv",
        pd.DataFrame(
            [
                {
                    "game_id": 1,
                    "player_count": 2,
                    "recommendation_level": "best",
                },
                {
                    "game_id": 2,
                    "player_count": 4,
                    "recommendation_level": "recommended",
                },
            ]
        ),
    )

    matrix, row_to_game, col_to_feature, game_to_row = build_content_feature_matrix(
        processed_dir=processed_dir,
        timestamp=ts,
        strong_weight=1.0,
        medium_weight=0.45,
        light_weight=0.2,
        publisher_weight=0.2,
        include_not_recommended=False,
    )

    assert matrix.shape[0] == 2
    assert matrix.shape[1] > 0
    assert matrix.nnz > 0
    assert row_to_game == {0: 1, 1: 2}
    assert game_to_row == {1: 0, 2: 1}
    assert any(name.startswith("mechanics:") for name in col_to_feature.values())
    assert any(name.startswith("playtime:") for name in col_to_feature.values())


def test_load_csv_handles_escaped_pipe_delimiter(tmp_path: Path) -> None:
    csv_path = tmp_path / "escaped_pipe.csv"
    csv_path.write_text(
        "game_id|boardgameartist_id|boardgameartist_name\n"
        "1|111|make\\|ad werbeagentur\n",
        encoding="utf-8",
    )

    df = _load_csv(csv_path)

    assert list(df.columns) == [
        "game_id",
        "boardgameartist_id",
        "boardgameartist_name",
    ]
    assert df.shape == (1, 3)
    assert str(df.loc[0, "boardgameartist_name"]) == "make|ad werbeagentur"
