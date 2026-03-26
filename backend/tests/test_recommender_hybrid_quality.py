from backend.app import recommender


def test_quality_score_prefers_more_ratings_for_close_bayes_scores() -> None:
    config = recommender.HybridScoringConfig(
        quality_bayes_scale=10.0,
        quality_confidence_k=1000.0,
        quality_confidence_floor=0.5,
    )

    # 8.0 with 1000 ratings should outrank 9.0 with 100 ratings
    # under the confidence-adjusted quality score.
    quality_many_votes = recommender._compute_quality_score(
        bayes_value=8.0,
        num_ratings=1000,
        config=config,
    )
    quality_few_votes = recommender._compute_quality_score(
        bayes_value=9.0,
        num_ratings=100,
        config=config,
    )

    assert quality_many_votes > quality_few_votes


def test_quality_score_increases_with_num_ratings_at_same_bayes() -> None:
    config = recommender.HybridScoringConfig(
        quality_bayes_scale=10.0,
        quality_confidence_k=1000.0,
        quality_confidence_floor=0.5,
    )

    low_votes = recommender._compute_quality_score(
        bayes_value=8.0,
        num_ratings=10,
        config=config,
    )
    high_votes = recommender._compute_quality_score(
        bayes_value=8.0,
        num_ratings=10000,
        config=config,
    )

    assert high_votes > low_votes
    assert 0.0 <= low_votes <= 1.0
    assert 0.0 <= high_votes <= 1.0


def test_normalized_hybrid_weights_default_sum_to_one() -> None:
    weights = recommender._normalized_hybrid_weights(recommender.HYBRID_SCORING_CONFIG)
    assert abs(sum(weights) - 1.0) < 1e-9
