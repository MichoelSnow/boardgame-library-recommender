from __future__ import annotations

import pandas as pd

from scripts.pax_labeling.resolve_existing_pax_titles import (
    MatchingRules,
    clean_raw_publisher,
    load_manual_fixes_csv,
    load_excluded_title_ids,
    normalize_text,
    resolve_matches,
    score_candidate,
)
from scripts.pax_labeling.matcher import has_promo_word


def test_clean_raw_publisher_removes_do_not_use_suffix() -> None:
    assert clean_raw_publisher("Asmodee - DO NOT USE") == "asmodee"
    assert clean_raw_publisher("Phalanx Games  - do not use") == "phalanx games"
    assert clean_raw_publisher("Fantasy Flight Games") == "fantasy flight games"


def test_normalize_text_unescapes_and_strips_spacing() -> None:
    assert normalize_text("  Café&nbsp;Games  ") == "cafe games"
    assert (
        normalize_text("A Matter of Honor, Sire", alnum_only=True)
        == "amatterofhonorsire"
    )


def test_normalize_text_treats_missing_values_as_empty() -> None:
    assert normalize_text(None) == ""
    assert normalize_text(pd.NA) == ""


def test_has_promo_word_matches_full_word_only() -> None:
    assert has_promo_word("Ticket to Ride Promo Pack")
    assert not has_promo_word("Promontory")
    assert not has_promo_word("Promotional Edition")


def test_score_candidate_penalizes_expansion_and_promo_independently() -> None:
    base_lookup = {
        1: {
            "name": "alpha",
            "title_norm": "alpha",
            "title_key": "alpha",
            "first_publisher_norm": "publisher",
            "yearpublished": 2020,
            "usersrated": 1000,
            "is_expansion_flag": 0,
        },
        2: {
            "name": "alpha",
            "title_norm": "alpha",
            "title_key": "alpha",
            "first_publisher_norm": "publisher",
            "yearpublished": 2020,
            "usersrated": 1000,
            "is_expansion_flag": 1,
        },
        3: {
            "name": "alpha promo",
            "title_norm": "alpha promo",
            "title_key": "alphapromo",
            "first_publisher_norm": "publisher",
            "yearpublished": 2020,
            "usersrated": 1000,
            "is_expansion_flag": 0,
        },
    }

    base = score_candidate(
        candidate_id=1,
        row_title_norm="alpha",
        row_title_key="alpha",
        row_publisher_norm="publisher",
        row_game_year=2021,
        row_bgg_id=None,
        games_lookup=base_lookup,
        publishers_by_game={1: {"publisher"}, 2: {"publisher"}, 3: {"publisher"}},
        versions_by_game={},
        title_priors=set(),
        forced_title_fix=None,
        forced_bgg_fix=None,
        rules=MatchingRules(),
    )
    expansion = score_candidate(
        candidate_id=2,
        row_title_norm="alpha",
        row_title_key="alpha",
        row_publisher_norm="publisher",
        row_game_year=2021,
        row_bgg_id=None,
        games_lookup=base_lookup,
        publishers_by_game={1: {"publisher"}, 2: {"publisher"}, 3: {"publisher"}},
        versions_by_game={},
        title_priors=set(),
        forced_title_fix=None,
        forced_bgg_fix=None,
        rules=MatchingRules(),
    )
    promo = score_candidate(
        candidate_id=3,
        row_title_norm="alpha promo",
        row_title_key="alphapromo",
        row_publisher_norm="publisher",
        row_game_year=2021,
        row_bgg_id=None,
        games_lookup=base_lookup,
        publishers_by_game={1: {"publisher"}, 2: {"publisher"}, 3: {"publisher"}},
        versions_by_game={},
        title_priors=set(),
        forced_title_fix=None,
        forced_bgg_fix=None,
        rules=MatchingRules(),
    )

    assert expansion.score < base.score
    assert promo.score < base.score
    assert expansion.is_expansion
    assert not base.is_expansion
    assert promo.has_promo_word
    assert not base.has_promo_word


def test_score_candidate_boosts_exact_title_plus_first_publisher_exact() -> None:
    games_lookup = {
        1: {
            "name": "alpha",
            "title_norm": "alpha",
            "title_key": "alpha",
            "first_publisher_norm": "publisher a",
            "yearpublished": 2020,
            "usersrated": 1000,
            "is_expansion_flag": 0,
        },
        2: {
            "name": "alpha",
            "title_norm": "alpha",
            "title_key": "alpha",
            "first_publisher_norm": "publisher b",
            "yearpublished": 2020,
            "usersrated": 1000,
            "is_expansion_flag": 0,
        },
    }
    all_publishers = {1: {"publisher a"}, 2: {"publisher a"}}

    exact_first = score_candidate(
        candidate_id=1,
        row_title_norm="alpha",
        row_title_key="alpha",
        row_publisher_norm="publisher a",
        row_game_year=2021,
        row_bgg_id=None,
        games_lookup=games_lookup,
        publishers_by_game=all_publishers,
        versions_by_game={},
        title_priors=set(),
        forced_title_fix=None,
        forced_bgg_fix=None,
        rules=MatchingRules(),
    )
    not_first = score_candidate(
        candidate_id=2,
        row_title_norm="alpha",
        row_title_key="alpha",
        row_publisher_norm="publisher a",
        row_game_year=2021,
        row_bgg_id=None,
        games_lookup=games_lookup,
        publishers_by_game=all_publishers,
        versions_by_game={},
        title_priors=set(),
        forced_title_fix=None,
        forced_bgg_fix=None,
        rules=MatchingRules(),
    )

    assert exact_first.publisher_match_type == "first_exact"
    assert not_first.publisher_match_type == "any_exact"
    assert exact_first.score > not_first.score + 1000


def test_score_candidate_prefers_exact_title_over_sequel_with_publisher_match() -> None:
    games_lookup = {
        68448: {
            "name": "7 Wonders",
            "title_norm": "7 wonders",
            "title_key": "7wonders",
            "first_publisher_norm": "repos production",
            "yearpublished": 2010,
            "usersrated": 112108,
            "is_expansion_flag": 0,
        },
        173346: {
            "name": "7 Wonders Duel",
            "title_norm": "7 wonders duel",
            "title_key": "7wondersduel",
            "first_publisher_norm": "repos production",
            "yearpublished": 2015,
            "usersrated": 107949,
            "is_expansion_flag": 0,
        },
    }
    publishers_by_game = {
        68448: {"repos production"},
        173346: {"asmodee"},
    }

    exact_title = score_candidate(
        candidate_id=68448,
        row_title_norm="7 wonders",
        row_title_key="7wonders",
        row_publisher_norm="asmodee",
        row_game_year=2014,
        row_bgg_id=None,
        games_lookup=games_lookup,
        publishers_by_game=publishers_by_game,
        versions_by_game={},
        title_priors=set(),
        forced_title_fix=None,
        forced_bgg_fix=None,
        rules=MatchingRules(),
    )
    sequel_with_publisher = score_candidate(
        candidate_id=173346,
        row_title_norm="7 wonders",
        row_title_key="7wonders",
        row_publisher_norm="asmodee",
        row_game_year=2014,
        row_bgg_id=None,
        games_lookup=games_lookup,
        publishers_by_game=publishers_by_game,
        versions_by_game={},
        title_priors=set(),
        forced_title_fix=None,
        forced_bgg_fix=None,
        rules=MatchingRules(),
    )

    assert exact_title.title_score == 100.0
    assert sequel_with_publisher.publisher_match
    assert exact_title.score > sequel_with_publisher.score


def test_load_manual_fixes_csv_reads_title_and_bgg_maps(tmp_path) -> None:
    manual_fixes_csv = tmp_path / "manual_fixes.csv"
    manual_fixes_csv.write_text(
        (
            "title_id, bgg_id, old_bgg_id\n"
            "387, 224, 89862\n"
            "2443, 224,\n"
            "bad, 100, 101\n"
            "500, bad, 102\n"
        ),
        encoding="utf-8",
    )

    bgg_fixes, title_fixes = load_manual_fixes_csv(manual_fixes_csv)

    assert bgg_fixes == {89862: 224, 101: 100}
    assert title_fixes == {387: 224, 2443: 224}


def test_load_excluded_title_ids_reads_csv_column(tmp_path) -> None:
    excluded_path = tmp_path / "title_ids_not_in_bgg.csv"
    excluded_path.write_text("title_id\n1\n2\nabc\n", encoding="utf-8")

    excluded = load_excluded_title_ids(excluded_path)
    assert excluded == {1, 2}


def test_resolve_matches_includes_bgg_name_columns() -> None:
    raw_df = pd.DataFrame(
        [
            {
                "title": "Catan",
                "title_id": 1,
                "game": "g1",
                "game_barcode": "b1",
                "publisher_name": "Kosmos",
                "bgg_id": None,
                "game_year": 1996,
                "status": 1,
            }
        ]
    )
    games_df = pd.DataFrame(
        [
            {
                "id": 13,
                "name": "CATAN",
                "yearpublished": 1995,
                "usersrated": 1000,
                "title_norm": "catan",
                "title_key": "catan",
                "first_publisher_norm": "kosmos",
            }
        ]
    )
    publishers_by_game = {13: {"kosmos"}}
    versions_by_game: dict[int, tuple[str, ...]] = {}

    result_df, review_df = resolve_matches(
        raw_df=raw_df,
        games_df=games_df,
        publishers_by_game=publishers_by_game,
        versions_by_game=versions_by_game,
        bgg_id_fixes={},
        title_id_fixes={},
        title_priors={},
        excluded_title_ids=set(),
        fuzzy_limit=5,
        fuzzy_cutoff=80,
        review_margin=75.0,
        rules=MatchingRules(),
    )

    assert len(result_df) == 1
    assert "new_bgg_name" in result_df.columns
    assert result_df.loc[0, "new_bgg_id"] == 13
    assert result_df.loc[0, "new_bgg_name"] == "CATAN"
    assert "original_bgg_name" in result_df.columns
    assert bool(result_df.loc[0, "excluded_title_id"]) is False
    assert bool(result_df.loc[0, "used_publisher_first_fallback"]) is False
    assert review_df.empty


def test_resolve_matches_skips_excluded_title_ids() -> None:
    raw_df = pd.DataFrame(
        [
            {
                "title": "Catan",
                "title_id": 42,
                "game": "g1",
                "game_barcode": "b1",
                "publisher_name": "Kosmos",
                "bgg_id": None,
                "game_year": 1996,
                "status": 1,
            }
        ]
    )
    games_df = pd.DataFrame(
        [
            {
                "id": 13,
                "name": "CATAN",
                "yearpublished": 1995,
                "usersrated": 1000,
                "title_norm": "catan",
                "title_key": "catan",
                "first_publisher_norm": "kosmos",
                "is_expansion_flag": 0,
            }
        ]
    )

    result_df, review_df = resolve_matches(
        raw_df=raw_df,
        games_df=games_df,
        publishers_by_game={13: {"kosmos"}},
        versions_by_game={},
        bgg_id_fixes={},
        title_id_fixes={},
        title_priors={},
        excluded_title_ids={42},
        fuzzy_limit=5,
        fuzzy_cutoff=80,
        review_margin=75.0,
        rules=MatchingRules(),
    )

    assert len(result_df) == 1
    assert pd.isna(result_df.loc[0, "new_bgg_id"])
    assert result_df.loc[0, "match_confidence"] == "excluded"
    assert result_df.loc[0, "match_reason"] == "excluded_title_id_list"
    assert bool(result_df.loc[0, "excluded_title_id"]) is True
    assert bool(result_df.loc[0, "used_publisher_first_fallback"]) is False
    assert review_df.empty


def test_resolve_matches_can_use_publisher_first_fallback() -> None:
    raw_df = pd.DataFrame(
        [
            {
                "title": "box art alias",
                "title_id": 5406,
                "game": "g1",
                "game_barcode": "b1",
                "publisher_name": "Chip Theory Games",
                "bgg_id": None,
                "game_year": 2025,
                "status": 1,
            }
        ]
    )
    games_df = pd.DataFrame(
        [
            {
                "id": 436590,
                "name": "20 Strong: Solar Sentinels",
                "yearpublished": 2024,
                "usersrated": 500,
                "title_norm": "20 strong solar sentinels",
                "title_key": "20strongsolarsentinels",
                "first_publisher_norm": "chip theory games",
                "is_expansion_flag": 0,
            },
            {
                "id": 999999,
                "name": "Unrelated Publisher Game",
                "yearpublished": 2024,
                "usersrated": 800,
                "title_norm": "unrelated publisher game",
                "title_key": "unrelatedpublishergame",
                "first_publisher_norm": "other publisher",
                "is_expansion_flag": 0,
            },
        ]
    )

    result_df, review_df = resolve_matches(
        raw_df=raw_df,
        games_df=games_df,
        publishers_by_game={436590: {"chip theory games"}, 999999: {"other publisher"}},
        versions_by_game={},
        bgg_id_fixes={},
        title_id_fixes={},
        title_priors={},
        excluded_title_ids=set(),
        fuzzy_limit=5,
        fuzzy_cutoff=90,
        review_margin=75.0,
        rules=MatchingRules(),
        publisher_first_fallback=True,
        publisher_first_max_candidates=50,
        publisher_first_title_score_threshold=95.0,
        publisher_first_margin_threshold=60.0,
    )

    assert len(result_df) == 1
    assert int(result_df.loc[0, "new_bgg_id"]) == 436590
    assert bool(result_df.loc[0, "used_publisher_first_fallback"]) is True
    assert result_df.loc[0, "match_reason"] == "publisher_first_fallback"
    assert len(review_df) <= 1


def test_year_gap_penalty_only_applies_when_enabled() -> None:
    games_lookup = {
        1: {
            "name": "countdown",
            "title_norm": "countdown",
            "title_key": "countdown",
            "first_publisher_norm": "publisher",
            "yearpublished": 1982,
            "usersrated": 100,
            "is_expansion_flag": 0,
        }
    }
    base = score_candidate(
        candidate_id=1,
        row_title_norm="countdown",
        row_title_key="countdown",
        row_publisher_norm="publisher",
        row_game_year=2025,
        row_bgg_id=None,
        games_lookup=games_lookup,
        publishers_by_game={1: {"publisher"}},
        versions_by_game={},
        title_priors=set(),
        forced_title_fix=None,
        forced_bgg_fix=None,
        rules=MatchingRules(year_gap_penalty_enabled=False),
    )
    penalized = score_candidate(
        candidate_id=1,
        row_title_norm="countdown",
        row_title_key="countdown",
        row_publisher_norm="publisher",
        row_game_year=2025,
        row_bgg_id=None,
        games_lookup=games_lookup,
        publishers_by_game={1: {"publisher"}},
        versions_by_game={},
        title_priors=set(),
        forced_title_fix=None,
        forced_bgg_fix=None,
        rules=MatchingRules(year_gap_penalty_enabled=True),
    )
    assert penalized.score < base.score


def test_subtitle_penalty_only_applies_when_enabled() -> None:
    games_lookup = {
        1: {
            "name": "cascadia",
            "title_norm": "cascadia",
            "title_key": "cascadia",
            "first_publisher_norm": "flatout games",
            "yearpublished": 2021,
            "usersrated": 1000,
            "is_expansion_flag": 0,
        }
    }
    base = score_candidate(
        candidate_id=1,
        row_title_norm="cascadia: rolling hills",
        row_title_key="cascadiarollinghills",
        row_publisher_norm="flatout games",
        row_game_year=2024,
        row_bgg_id=None,
        games_lookup=games_lookup,
        publishers_by_game={1: {"flatout games"}},
        versions_by_game={},
        title_priors=set(),
        forced_title_fix=None,
        forced_bgg_fix=None,
        rules=MatchingRules(subtitle_penalty_enabled=False),
    )
    penalized = score_candidate(
        candidate_id=1,
        row_title_norm="cascadia: rolling hills",
        row_title_key="cascadiarollinghills",
        row_publisher_norm="flatout games",
        row_game_year=2024,
        row_bgg_id=None,
        games_lookup=games_lookup,
        publishers_by_game={1: {"flatout games"}},
        versions_by_game={},
        title_priors=set(),
        forced_title_fix=None,
        forced_bgg_fix=None,
        rules=MatchingRules(subtitle_penalty_enabled=True),
    )
    assert penalized.score < base.score


def test_publisher_suffix_normalization_enables_exact_match() -> None:
    games_lookup = {
        1: {
            "name": "3-2-1 countdown",
            "title_norm": "3 2 1 countdown",
            "title_key": "321countdown",
            "first_publisher_norm": "grandpa beck's games",
            "yearpublished": 2025,
            "usersrated": 100,
            "is_expansion_flag": 0,
        }
    }
    without = score_candidate(
        candidate_id=1,
        row_title_norm="countdown",
        row_title_key="countdown",
        row_publisher_norm="grandpa beck's",
        row_game_year=2025,
        row_bgg_id=None,
        games_lookup=games_lookup,
        publishers_by_game={1: {"grandpa beck's games"}},
        versions_by_game={},
        title_priors=set(),
        forced_title_fix=None,
        forced_bgg_fix=None,
        rules=MatchingRules(publisher_suffix_normalization_enabled=False),
    )
    with_norm = score_candidate(
        candidate_id=1,
        row_title_norm="countdown",
        row_title_key="countdown",
        row_publisher_norm="grandpa beck's",
        row_game_year=2025,
        row_bgg_id=None,
        games_lookup=games_lookup,
        publishers_by_game={1: {"grandpa beck's games"}},
        versions_by_game={},
        title_priors=set(),
        forced_title_fix=None,
        forced_bgg_fix=None,
        rules=MatchingRules(publisher_suffix_normalization_enabled=True),
    )
    assert with_norm.publisher_match_type == "first_exact"
    assert with_norm.score > without.score


def test_generic_title_guard_penalizes_weak_support() -> None:
    games_lookup = {
        1: {
            "name": "countdown",
            "title_norm": "countdown",
            "title_key": "countdown",
            "first_publisher_norm": "britannia games",
            "yearpublished": 1982,
            "usersrated": 100,
            "is_expansion_flag": 0,
        }
    }
    base = score_candidate(
        candidate_id=1,
        row_title_norm="countdown",
        row_title_key="countdown",
        row_publisher_norm="grandpa beck's",
        row_game_year=2025,
        row_bgg_id=None,
        games_lookup=games_lookup,
        publishers_by_game={1: {"britannia games"}},
        versions_by_game={},
        title_priors=set(),
        forced_title_fix=None,
        forced_bgg_fix=None,
        rules=MatchingRules(generic_title_guard_enabled=False),
    )
    guarded = score_candidate(
        candidate_id=1,
        row_title_norm="countdown",
        row_title_key="countdown",
        row_publisher_norm="grandpa beck's",
        row_game_year=2025,
        row_bgg_id=None,
        games_lookup=games_lookup,
        publishers_by_game={1: {"britannia games"}},
        versions_by_game={},
        title_priors=set(),
        forced_title_fix=None,
        forced_bgg_fix=None,
        rules=MatchingRules(generic_title_guard_enabled=True),
    )
    assert guarded.score < base.score


def test_popularity_override_bypasses_year_gap_and_generic_penalties() -> None:
    games_lookup = {
        1: {
            "name": "blood rage",
            "title_norm": "blood rage",
            "title_key": "bloodrage",
            "first_publisher_norm": "cool mini or not",
            "yearpublished": 2015,
            "usersrated": 51520,
            "is_expansion_flag": 0,
        },
        2: {
            "name": "blood rage",
            "title_norm": "blood rage",
            "title_key": "bloodrage",
            "first_publisher_norm": "cool mini or not",
            "yearpublished": 2015,
            "usersrated": 50,
            "is_expansion_flag": 0,
        },
    }
    rules_with_override = MatchingRules(
        year_gap_penalty_enabled=True,
        generic_title_guard_enabled=True,
        popularity_override_enabled=True,
        popularity_override_min_usersrated=3000,
        popularity_override_min_title_score=95.0,
    )
    rules_without_override = MatchingRules(
        year_gap_penalty_enabled=True,
        generic_title_guard_enabled=True,
        popularity_override_enabled=False,
    )

    high_pop_with_override = score_candidate(
        candidate_id=1,
        row_title_norm="blood rage",
        row_title_key="bloodrage",
        row_publisher_norm="cmon",
        row_game_year=2025,
        row_bgg_id=None,
        games_lookup=games_lookup,
        publishers_by_game={1: {"cool mini or not"}, 2: {"cool mini or not"}},
        versions_by_game={},
        title_priors=set(),
        forced_title_fix=None,
        forced_bgg_fix=None,
        rules=rules_with_override,
    )
    high_pop_without_override = score_candidate(
        candidate_id=1,
        row_title_norm="blood rage",
        row_title_key="bloodrage",
        row_publisher_norm="cmon",
        row_game_year=2025,
        row_bgg_id=None,
        games_lookup=games_lookup,
        publishers_by_game={1: {"cool mini or not"}, 2: {"cool mini or not"}},
        versions_by_game={},
        title_priors=set(),
        forced_title_fix=None,
        forced_bgg_fix=None,
        rules=rules_without_override,
    )
    low_pop_with_override = score_candidate(
        candidate_id=2,
        row_title_norm="blood rage",
        row_title_key="bloodrage",
        row_publisher_norm="cmon",
        row_game_year=2025,
        row_bgg_id=None,
        games_lookup=games_lookup,
        publishers_by_game={1: {"cool mini or not"}, 2: {"cool mini or not"}},
        versions_by_game={},
        title_priors=set(),
        forced_title_fix=None,
        forced_bgg_fix=None,
        rules=rules_with_override,
    )

    assert high_pop_with_override.score > high_pop_without_override.score
    assert high_pop_with_override.score > low_pop_with_override.score
