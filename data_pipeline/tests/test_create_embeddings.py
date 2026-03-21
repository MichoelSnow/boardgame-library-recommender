import numpy as np
import pandas as pd
import duckdb
import pytest

from data_pipeline.src.features.create_embeddings import (
    GameRecommender,
    load_wide_ratings_from_duckdb,
    resolve_embeddings_output_dir,
)


def test_create_rating_matrix_builds_expected_shape_and_values():
    df = pd.DataFrame(
        [
            {"id": 101, "8.0": ["u1", "u2"], "9.0": ["u3"]},
            {"id": 102, "8.0": ["u2"], "9.0": []},
        ]
    )

    recommender = GameRecommender(min_ratings_per_user=1)
    matrix = recommender._create_rating_matrix(df)

    assert matrix.shape == (3, 2)
    assert set(recommender.user_mapping.keys()) == {"u1", "u2", "u3"}
    assert set(recommender.game_mapping.keys()) == {101, 102}

    dense = matrix.toarray()
    assert dense[recommender.user_mapping["u1"], recommender.game_mapping[101]] == 8.0
    assert dense[recommender.user_mapping["u2"], recommender.game_mapping[101]] == 8.0
    assert dense[recommender.user_mapping["u2"], recommender.game_mapping[102]] == 8.0
    assert dense[recommender.user_mapping["u3"], recommender.game_mapping[101]] == 9.0


def test_filter_users_drops_sparse_raters():
    df = pd.DataFrame(
        [
            {"id": 201, "7.0": ["u1", "u2"]},
            {"id": 202, "8.0": ["u1"]},
        ]
    )
    recommender = GameRecommender(min_ratings_per_user=2)
    matrix = recommender._create_rating_matrix(df)

    filtered = recommender._filter_users(matrix)

    # Only u1 has >= 2 ratings.
    assert filtered.shape == (1, 2)
    assert np.count_nonzero(filtered.toarray()) == 2


def test_fit_sets_embeddings_with_expected_game_axis():
    df = pd.DataFrame(
        [
            {"id": 301, "6.0": ["u1"], "9.0": ["u2"]},
            {"id": 302, "7.0": ["u1", "u2"], "10.0": ["u3"]},
            {"id": 303, "8.0": ["u3"], "9.0": ["u1"]},
        ]
    )

    recommender = GameRecommender(min_ratings_per_user=1)
    recommender.fit(df)

    assert recommender.rating_matrix is not None
    assert recommender.game_embeddings is not None
    # Embeddings are game vectors, so rows should match number of games.
    assert recommender.game_embeddings.shape[0] == 3


def test_load_wide_ratings_from_duckdb(tmp_path):
    db_path = tmp_path / "boardgame_ratings_123.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            CREATE TABLE boardgame_ratings (
                game_id BIGINT,
                rating_round DOUBLE,
                username TEXT
            )
            """
        )
        con.execute(
            """
            INSERT INTO boardgame_ratings (game_id, rating_round, username) VALUES
            (10, 8.0, 'u1'),
            (10, 8.0, 'u2'),
            (10, 9.0, 'u3'),
            (20, 7.0, 'u1')
            """
        )
    finally:
        con.close()

    df = load_wide_ratings_from_duckdb(db_path)
    assert set(df["id"].tolist()) == {10, 20}
    row_10 = df.loc[df["id"] == 10].iloc[0]
    assert set(row_10["8.0"]) == {"u1", "u2"}
    assert row_10["9.0"] == ["u3"]


def test_load_wide_ratings_from_duckdb_raises_if_table_missing(tmp_path):
    db_path = tmp_path / "empty.duckdb"
    con = duckdb.connect(str(db_path))
    con.close()
    with pytest.raises(ValueError, match="boardgame_ratings"):
        load_wide_ratings_from_duckdb(db_path)


def test_resolve_embeddings_output_dir_points_to_repo_backend_database():
    output_dir = resolve_embeddings_output_dir()
    assert output_dir.as_posix().endswith("/backend/database")
