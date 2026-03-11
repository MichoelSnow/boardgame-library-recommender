import numpy as np
import pandas as pd

from data_pipeline.src.features.create_embeddings import GameRecommender


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
