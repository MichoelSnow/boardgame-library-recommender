from __future__ import annotations

import pandas as pd
import pytest

from scripts.pax_labeling.finalize_pax_title_corrections import (
    OUTPUT_COLUMNS,
    build_cleaned_dataframe,
)


def test_build_cleaned_dataframe_applies_bgg_and_title_rules() -> None:
    source_df = pd.DataFrame(
        [
            {
                "title": "Original A",
                "title_id": 1,
                "game": "g1",
                "game_barcode": "b1",
                "bgg_id": 10,
                "new_bgg_id": 100,
                "new_bgg_name": "Original A",
                "match_confidence": "low",
                "status": 1,
            },
            {
                "title": "Original B",
                "title_id": 2,
                "game": "g2",
                "game_barcode": "b2",
                "bgg_id": 20,
                "new_bgg_id": 200,
                "new_bgg_name": "Original B",
                "match_confidence": "medium",
                "status": 2,
            },
            {
                "title": "Catan",
                "title_id": 3,
                "game": "g3",
                "game_barcode": "b3",
                "bgg_id": 30,
                "new_bgg_id": 300,
                "new_bgg_name": "CATAN",
                "match_confidence": "high",
                "status": 1,
            },
            {
                "title": "Tiny Epic",
                "title_id": 4,
                "game": "g4",
                "game_barcode": "b4",
                "bgg_id": 40,
                "new_bgg_id": 400,
                "new_bgg_name": "Totally Different Name",
                "match_confidence": "low",
                "status": 0,
            },
        ]
    )

    cleaned_df, similarity = build_cleaned_dataframe(
        source_df,
        title_match_threshold=95.0,
        title_similarity_metric="token_sort",
    )

    assert cleaned_df.columns.tolist() == OUTPUT_COLUMNS

    # low/medium with non-zero status keep original values
    assert int(cleaned_df.loc[0, "bgg_id"]) == 10
    assert int(cleaned_df.loc[1, "bgg_id"]) == 20
    assert not bool(cleaned_df.loc[0, "has_updated_bgg_id"])
    assert not bool(cleaned_df.loc[1, "has_updated_bgg_id"])
    assert cleaned_df.loc[0, "title"] == "Original A"
    assert cleaned_df.loc[1, "title"] == "Original B"
    assert not bool(cleaned_df.loc[0, "has_updated_title"])
    assert not bool(cleaned_df.loc[1, "has_updated_title"])

    # high confidence updates bgg_id; title updates if above threshold
    assert int(cleaned_df.loc[2, "bgg_id"]) == 300
    assert bool(cleaned_df.loc[2, "has_updated_bgg_id"])
    assert cleaned_df.loc[2, "title"] == "CATAN"
    assert bool(cleaned_df.loc[2, "has_updated_title"])
    assert float(similarity.loc[2]) >= 95.0
    assert float(cleaned_df.loc[2, "match"]) >= 95.0

    # status=0 updates bgg_id even with low confidence
    assert int(cleaned_df.loc[3, "bgg_id"]) == 400
    assert bool(cleaned_df.loc[3, "has_updated_bgg_id"])
    # but keep title when similarity is below threshold
    assert cleaned_df.loc[3, "title"] == "Tiny Epic"
    assert not bool(cleaned_df.loc[3, "has_updated_title"])
    assert float(similarity.loc[3]) < 95.0
    assert float(cleaned_df.loc[3, "match"]) < 95.0


def test_build_cleaned_dataframe_requires_columns() -> None:
    source_df = pd.DataFrame([{"title": "Only Title"}])

    with pytest.raises(ValueError, match="missing required columns"):
        build_cleaned_dataframe(
            source_df,
            title_match_threshold=95.0,
            title_similarity_metric="token_sort",
        )


def test_build_cleaned_dataframe_applies_manual_title_fix_ground_truth() -> None:
    source_df = pd.DataFrame(
        [
            {
                "title": "Quacks",
                "title_id": 3972,
                "game": "g3972",
                "game_barcode": "b3972",
                "bgg_id": None,
                "new_bgg_id": 269259,
                "new_bgg_name": "The Quacks of Quedlinburg: The Herb Witches",
                "match_confidence": "high",
                "status": 1,
            }
        ]
    )

    cleaned_df, _ = build_cleaned_dataframe(
        source_df,
        title_match_threshold=70.0,
        title_similarity_metric="token_sort",
        manual_title_fixes={3972: 244521},
        keep_name_title_ids=set(),
        bgg_name_lookup={244521: "Quacks"},
    )

    assert int(cleaned_df.loc[0, "bgg_id"]) == 244521
    assert bool(cleaned_df.loc[0, "has_updated_bgg_id"])
    assert cleaned_df.loc[0, "title"] == "Quacks"


def test_build_cleaned_dataframe_keep_name_prevents_title_replacement() -> None:
    source_df = pd.DataFrame(
        [
            {
                "title": "Catan",
                "title_id": 5555,
                "game": "g5555",
                "game_barcode": "b5555",
                "bgg_id": 13,
                "new_bgg_id": 13,
                "new_bgg_name": "CATAN",
                "match_confidence": "high",
                "status": 1,
            }
        ]
    )

    cleaned_df, similarity = build_cleaned_dataframe(
        source_df,
        title_match_threshold=70.0,
        title_similarity_metric="token_sort",
        keep_name_title_ids={5555},
    )

    assert float(similarity.loc[0]) >= 70.0
    assert cleaned_df.loc[0, "title"] == "Catan"
    assert not bool(cleaned_df.loc[0, "has_updated_title"])
