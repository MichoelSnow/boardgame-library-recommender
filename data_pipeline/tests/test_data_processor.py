from pathlib import Path

import duckdb
import pandas as pd

from data_pipeline.src.transform import data_processor


def _build_basic_info_row(game_id: int, rank: int) -> dict:
    row = {
        "id": game_id,
        "name": f"Game {game_id}",
        "thumbnail": f"https://example.com/{game_id}_thumb.jpg",
        "image": f"https://example.com/{game_id}.jpg",
        "description": "desc",
        "bayesaverage": 7.5,
        "average": 7.8,
        "stddev": 1.1,
        "median": 0.0,
        "averageweight": 2.5,
        "rank": rank,
    }

    int_cols = [
        "yearpublished",
        "usersrated",
        "is_expansion",
        "abstracts_rank",
        "cgs_rank",
        "childrensgames_rank",
        "familygames_rank",
        "partygames_rank",
        "strategygames_rank",
        "thematic_rank",
        "wargames_rank",
        "minplayers",
        "maxplayers",
        "playingtime",
        "minplaytime",
        "maxplaytime",
        "minage",
        "owned",
        "trading",
        "wanting",
        "wishing",
        "numcomments",
        "numweights",
        "numratings",
    ]
    for col in int_cols:
        row[col] = 1
    return row


def test_save_basic_info_writes_expected_columns_and_rank_zero_as_null(tmp_path):
    timestamp = 111
    output_file_base = str(tmp_path / "processed_games")
    df = pd.DataFrame(
        [
            _build_basic_info_row(game_id=1, rank=0),
            _build_basic_info_row(game_id=2, rank=10),
        ]
    )

    data_processor.save_basic_info(df, output_file_base, timestamp)

    output_path = Path(f"{output_file_base}_data_{timestamp}.csv")
    assert output_path.exists()

    saved = pd.read_csv(output_path, sep="|", escapechar="\\")
    assert set(["id", "name", "thumbnail", "image", "description"]).issubset(
        saved.columns
    )
    assert "avg_box_volume" in saved.columns
    assert pd.isna(saved.loc[saved["id"] == 1, "rank"]).all()
    assert int(saved.loc[saved["id"] == 2, "rank"].iloc[0]) == 10


def test_combine_crawler_data_applies_exclude_ids_before_save(monkeypatch, tmp_path):
    ranks = pd.DataFrame(
        [
            {"id": 1, "rank": 10, "queried_at_utc": "2026-01-01T00:00:00Z"},
            {"id": 2, "rank": 20, "queried_at_utc": "2026-01-01T00:00:00Z"},
        ]
    )
    ranks_path = tmp_path / "ranks.csv"
    data_path = tmp_path / "boardgame_data_123.duckdb"
    ranks.to_csv(ranks_path, sep="|", index=False)
    with duckdb.connect(str(data_path)) as conn:
        conn.execute(
            """
            CREATE TABLE boardgame_data (
                id BIGINT PRIMARY KEY,
                payload_json TEXT
            )
            """
        )
        payload_rows = [
            {"id": 1, "payload_json": '{"id": 1, "name": "Keep"}'},
            {"id": 2, "payload_json": '{"id": 2, "name": "Drop"}'},
        ]
        conn.register("payload_rows", pd.DataFrame(payload_rows))
        conn.execute(
            """
            INSERT INTO boardgame_data (id, payload_json)
            SELECT id, payload_json
            FROM payload_rows
            """
        )
        conn.unregister("payload_rows")

    captured = {}

    def _capture(df_merged, output_file_base, timestamp):
        captured["df"] = df_merged.copy()
        captured["output_file_base"] = output_file_base
        captured["timestamp"] = timestamp

    monkeypatch.setattr(data_processor, "save_basic_info", _capture)
    monkeypatch.setattr(
        data_processor, "save_dict_id_cols", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        data_processor, "save_suggested_num_players", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(data_processor, "save_versions", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        data_processor, "save_language_dependence", lambda *args, **kwargs: None
    )

    data_processor.combine_crawler_data(
        ranks_file=str(ranks_path),
        data_file=str(data_path),
        output_file_base=str(tmp_path / "processed_games"),
        timestamp=999,
        exclude_ids=[2],
    )

    merged = captured["df"]
    assert merged["id"].tolist() == [1]
    assert merged["rank"].tolist() == [10]
    assert "queried_at_utc" not in merged.columns
    assert captured["timestamp"] == 999


def test_save_suggested_num_players_handles_total_votes_int_entry(tmp_path):
    timestamp = 222
    output_file_base = str(tmp_path / "processed_games")
    df = pd.DataFrame(
        [
            {
                "id": 1,
                "suggested_numplayers": {
                    "total_votes": 100,
                    "1": {
                        "Best": 20,
                        "Recommended": 30,
                        "Not Recommended": 10,
                        "total_votes": 60,
                    },
                    "2": {
                        "Best": 25,
                        "Recommended": 35,
                        "Not Recommended": 5,
                        "total_votes": 65,
                    },
                },
            }
        ]
    )

    data_processor.save_suggested_num_players(df, output_file_base, timestamp)

    output_path = Path(f"{output_file_base}_suggested_num_players_{timestamp}.csv")
    assert output_path.exists()
    saved = pd.read_csv(output_path, sep="|", escapechar="\\")
    assert len(saved) == 2
    assert set(saved["player_count"].tolist()) == {1, 2}


def test_add_avg_box_volume_uses_english_versions_only():
    df = pd.DataFrame(
        [
            {
                "id": 1,
                "versions": [
                    {"language": "english", "length": 10, "width": 20, "depth": 3},
                    {"language": "English", "length": 8, "width": 10, "depth": 2},
                    {"language": "german", "length": 100, "width": 100, "depth": 10},
                ],
            },
            {
                "id": 2,
                "versions": [
                    {"language": "english", "length": 5, "width": 5, "depth": 5}
                ],
            },
            {"id": 3, "versions": []},
        ]
    )

    out = data_processor.add_avg_box_volume(df)

    # game 1: round((600 + 160)/2) = 380
    assert int(out.loc[out["id"] == 1, "avg_box_volume"].iloc[0]) == 380
    assert int(out.loc[out["id"] == 2, "avg_box_volume"].iloc[0]) == 125
    assert pd.isna(out.loc[out["id"] == 3, "avg_box_volume"].iloc[0])
