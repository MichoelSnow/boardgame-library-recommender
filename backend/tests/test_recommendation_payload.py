from backend.app import recommender, schemas


def test_build_recommendation_payload_adds_score_without_mutating_input() -> None:
    record = {
        "id": 42,
        "name": "Test Game",
        "min_players": 1,
    }

    payload = recommender.build_recommendation_payload(record, 0.987)

    assert payload["id"] == 42
    assert payload["name"] == "Test Game"
    assert payload["recommendation_score"] == 0.987
    assert "recommendation_score" not in record


def test_recommendation_schema_accepts_scalar_payload() -> None:
    payload = schemas.RecommendationGameOut.model_validate(
        {
            "id": 7,
            "name": "Payload Game",
            "recommendation_score": 0.55,
        }
    )

    assert payload.id == 7
    assert payload.name == "Payload Game"
    assert payload.recommendation_score == 0.55
