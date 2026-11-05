from __future__ import annotations

import pandas as pd
import pytest

from scripts.pax_labeling.match_new_pax_games import OUTPUT_COLUMNS, build_best_matches


def _games_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "id": 68448,
                "name": "7 Wonders",
                "title_norm": "7 wonders",
                "title_key": "7wonders",
                "first_publisher_norm": "repos production",
                "yearpublished": 2010,
                "usersrated": 100000,
                "is_expansion_flag": 0,
            },
            {
                "id": 173346,
                "name": "7 Wonders Duel",
                "title_norm": "7 wonders duel",
                "title_key": "7wondersduel",
                "first_publisher_norm": "repos production",
                "yearpublished": 2015,
                "usersrated": 100000,
                "is_expansion_flag": 0,
            },
        ]
    )


def test_build_best_matches_returns_expected_columns_and_best_candidate() -> None:
    input_df = pd.DataFrame(
        [{"title": "7 Wonders", "publisher_name": "Repos Production"}]
    )
    matched_df = build_best_matches(
        input_df,
        games_df=_games_df(),
        publishers_by_game={
            68448: {"repos production", "asmodee"},
            173346: {"repos production"},
        },
        versions_by_game={},
        publishers_display_by_game={
            68448: ("Repos Production", "Asmodee"),
            173346: ("Repos Production",),
        },
        fuzzy_limit=25,
        fuzzy_cutoff=84,
        publisher_first_max_candidates=250,
    )

    assert matched_df.columns.tolist() == OUTPUT_COLUMNS
    assert int(matched_df.loc[0, "bgg_id"]) == 68448
    assert matched_df.loc[0, "bgg_name"] == "7 Wonders"
    assert matched_df.loc[0, "bgg_publishers"] == "Repos Production | Asmodee"
    assert int(matched_df.loc[0, "year_published"]) == 2010


def test_build_best_matches_unresolved_row_returns_empty_bgg_fields() -> None:
    input_df = pd.DataFrame([{"title": "Not A Real Game", "publisher_name": "Nope"}])
    matched_df = build_best_matches(
        input_df,
        games_df=_games_df(),
        publishers_by_game={68448: {"repos production"}, 173346: {"repos production"}},
        versions_by_game={},
        publishers_display_by_game={},
        fuzzy_limit=25,
        fuzzy_cutoff=84,
        publisher_first_max_candidates=250,
    )

    assert pd.isna(matched_df.loc[0, "bgg_id"])
    assert pd.isna(matched_df.loc[0, "bgg_name"])
    assert pd.isna(matched_df.loc[0, "bgg_publishers"])
    assert pd.isna(matched_df.loc[0, "year_published"])


def test_build_best_matches_requires_title_and_publisher_columns() -> None:
    bad_input = pd.DataFrame([{"title": "Only Title"}])

    with pytest.raises(ValueError, match="missing required columns"):
        build_best_matches(
            bad_input,
            games_df=_games_df(),
            publishers_by_game={},
            versions_by_game={},
            publishers_display_by_game={},
            fuzzy_limit=25,
            fuzzy_cutoff=84,
            publisher_first_max_candidates=250,
        )
