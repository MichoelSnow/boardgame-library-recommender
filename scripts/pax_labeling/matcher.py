"""Shared BGG candidate matching utilities for PAX labeling workflows."""

from __future__ import annotations

import html
import logging
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from rapidfuzz import fuzz


logger = logging.getLogger(__name__)


DO_NOT_USE_PATTERN = re.compile(r"\s*-\s*do\s+not\s+use.*$", re.IGNORECASE)
SQUEEZE_SPACES_PATTERN = re.compile(r"\s+")
NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")
PROMO_WORD_PATTERN = re.compile(r"\bpromo\b", re.IGNORECASE)
ALNUM_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

EXPANSION_SCORE_PENALTY = 200.0
PROMO_SCORE_PENALTY = 175.0
TITLE_EXACT_MATCH_BONUS = 1200.0
TITLE_FIRST_PUBLISHER_EXACT_BONUS = 2200.0
PUBLISHER_SUFFIX_TOKENS = {
    "game",
    "games",
    "inc",
    "llc",
    "ltd",
    "co",
    "company",
}

BggFixMap = dict[int, int]
TitleFixMap = dict[int, int]
TitlePriorMap = dict[int, set[int]]


@dataclass(frozen=True)
class CandidateScore:
    bgg_id: int
    bgg_name: str
    score: float
    dimension_count: int
    title_score: float
    title_match: bool
    publisher_match: bool
    publisher_match_type: str
    year_match: bool
    id_match: bool
    yearpublished: int | None
    usersrated: int | None
    pax_prior: bool
    manual_title_fix: bool
    manual_bgg_fix: bool
    is_expansion: bool
    has_promo_word: bool


@dataclass(frozen=True)
class MatchingRules:
    year_gap_penalty_enabled: bool = False
    year_gap_soft_threshold: int = 5
    year_gap_hard_threshold: int = 15
    year_gap_soft_penalty: float = 250.0
    year_gap_hard_penalty: float = 900.0
    subtitle_penalty_enabled: bool = False
    subtitle_miss_penalty: float = 600.0
    publisher_suffix_normalization_enabled: bool = False
    generic_title_guard_enabled: bool = False
    generic_title_max_tokens: int = 1
    generic_title_max_length: int = 10
    generic_title_without_publisher_penalty: float = 450.0
    generic_title_without_year_penalty: float = 200.0
    popularity_override_enabled: bool = True
    popularity_override_min_usersrated: int = 3000
    popularity_override_min_title_score: float = 95.0


def normalize_text(value: Any, *, alnum_only: bool = False) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value)
    if not text:
        return ""
    text = html.unescape(text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.casefold().strip()
    text = SQUEEZE_SPACES_PATTERN.sub(" ", text)
    if alnum_only:
        text = NON_ALNUM_PATTERN.sub("", text)
    return text


def clean_raw_publisher(value: Any) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    text = DO_NOT_USE_PATTERN.sub("", text).strip()
    return SQUEEZE_SPACES_PATTERN.sub(" ", text)


def has_promo_word(value: Any) -> bool:
    return bool(PROMO_WORD_PATTERN.search(normalize_text(value)))


def tokenize_alnum(value: Any) -> list[str]:
    return ALNUM_TOKEN_PATTERN.findall(normalize_text(value))


def canonicalize_publisher(value: Any) -> str:
    tokens = [
        token for token in tokenize_alnum(value) if token not in PUBLISHER_SUFFIX_TOKENS
    ]
    return " ".join(tokens)


def subtitle_tokens(value: Any) -> set[str]:
    normalized = normalize_text(value)
    if ":" not in normalized:
        return set()
    suffix = normalized.split(":", 1)[1]
    return set(ALNUM_TOKEN_PATTERN.findall(suffix))


def should_apply_subtitle_penalty(
    *,
    row_title_norm: str,
    candidate_title_norm: str,
) -> bool:
    row_suffix_tokens = subtitle_tokens(row_title_norm)
    if not row_suffix_tokens:
        return False
    candidate_tokens = set(ALNUM_TOKEN_PATTERN.findall(candidate_title_norm))
    return row_suffix_tokens.isdisjoint(candidate_tokens)


def is_generic_title(row_title_norm: str, rules: MatchingRules) -> bool:
    tokens = tokenize_alnum(row_title_norm)
    if not tokens:
        return False
    title_len = len("".join(tokens))
    return (
        len(tokens) <= rules.generic_title_max_tokens
        or title_len <= rules.generic_title_max_length
    )


def load_manual_fixes_csv(csv_path: Path) -> tuple[BggFixMap, TitleFixMap]:
    fixes_df = pd.read_csv(csv_path, skipinitialspace=True)
    fixes_df.columns = [str(column).strip().casefold() for column in fixes_df.columns]

    target_bgg_col = "new_bgg_id" if "new_bgg_id" in fixes_df.columns else "bgg_id"
    if target_bgg_col not in fixes_df.columns:
        raise ValueError(
            f"Manual fixes CSV at {csv_path} must include bgg_id or new_bgg_id column"
        )

    target_bgg_series = pd.to_numeric(fixes_df[target_bgg_col], errors="coerce")
    bgg_id_fixes: BggFixMap = {}
    title_id_fixes: TitleFixMap = {}

    title_col = "title_id" if "title_id" in fixes_df.columns else None
    if title_col is None and "min_titles_id" in fixes_df.columns:
        title_col = "min_titles_id"
    if title_col is not None:
        title_series = pd.to_numeric(fixes_df[title_col], errors="coerce")
        valid_title = title_series.notna() & target_bgg_series.notna()
        for title_id, bgg_id in zip(
            title_series[valid_title], target_bgg_series[valid_title], strict=False
        ):
            title_id_fixes[int(title_id)] = int(bgg_id)

    source_bgg_col = None
    for candidate_col in ("old_bgg_id", "source_bgg_id", "from_bgg_id", "bgg_id_old"):
        if candidate_col in fixes_df.columns:
            source_bgg_col = candidate_col
            break
    if source_bgg_col is not None:
        source_bgg_series = pd.to_numeric(fixes_df[source_bgg_col], errors="coerce")
        valid_bgg = source_bgg_series.notna() & target_bgg_series.notna()
        for old_bgg_id, new_bgg_id in zip(
            source_bgg_series[valid_bgg], target_bgg_series[valid_bgg], strict=False
        ):
            bgg_id_fixes[int(old_bgg_id)] = int(new_bgg_id)

    logger.info(
        "Loaded manual CSV fixes: %s by bgg_id, %s by title_id from %s",
        len(bgg_id_fixes),
        len(title_id_fixes),
        csv_path,
    )
    return bgg_id_fixes, title_id_fixes


def build_title_prior_map(prior_path: Path) -> TitlePriorMap:
    prior_df = pd.read_csv(prior_path, sep="|", encoding="utf-8")
    prior_df["min_titles_id"] = pd.to_numeric(
        prior_df["min_titles_id"], errors="coerce"
    )
    prior_df["bgg_id"] = pd.to_numeric(prior_df["bgg_id"], errors="coerce")
    prior_df = prior_df.dropna(subset=["min_titles_id", "bgg_id"])

    prior_map: TitlePriorMap = defaultdict(set)
    for row in prior_df.itertuples(index=False):
        prior_map[int(row.min_titles_id)].add(int(row.bgg_id))

    logger.info("Loaded title priors from %s title_ids", len(prior_map))
    return prior_map


def load_excluded_title_ids(path: Path) -> set[int]:
    excluded_df = pd.read_csv(path, comment="#")
    if excluded_df.empty:
        logger.info("Excluded title-id list at %s is empty", path)
        return set()

    if "title_id" in excluded_df.columns:
        title_ids = excluded_df["title_id"]
    else:
        title_ids = excluded_df.iloc[:, 0]

    excluded_ids = {
        int(value)
        for value in pd.to_numeric(title_ids, errors="coerce").dropna().astype("int64")
    }
    logger.info("Loaded %s excluded title_ids from %s", len(excluded_ids), path)
    return excluded_ids


def load_bgg_data(
    ranks_path: Path,
    first_publishers_path: Path,
    all_publishers_path: Path,
    versions_path: Path,
) -> tuple[pd.DataFrame, dict[int, set[str]], dict[int, tuple[str, ...]]]:
    ranks_df = pd.read_csv(
        ranks_path,
        sep="|",
        escapechar="\\",
        low_memory=False,
    )
    ranks_df = ranks_df[
        ["id", "name", "yearpublished", "usersrated", "is_expansion"]
    ].copy()
    ranks_df["id"] = pd.to_numeric(ranks_df["id"], errors="coerce")
    ranks_df = ranks_df.dropna(subset=["id"])
    ranks_df["id"] = ranks_df["id"].astype("int64")
    ranks_df["yearpublished"] = pd.to_numeric(
        ranks_df["yearpublished"], errors="coerce"
    ).astype("Int64")
    ranks_df["usersrated"] = pd.to_numeric(
        ranks_df["usersrated"], errors="coerce"
    ).astype("Int64")
    is_expansion_num = pd.to_numeric(ranks_df["is_expansion"], errors="coerce").fillna(
        0
    )
    is_expansion_text = (
        ranks_df["is_expansion"]
        .astype(str)
        .str.strip()
        .str.casefold()
        .isin({"true", "t", "yes", "y"})
    )
    ranks_df["is_expansion_flag"] = (is_expansion_num.gt(0) | is_expansion_text).astype(
        "int64"
    )
    ranks_df = ranks_df.drop(columns=["is_expansion"])
    ranks_df["name"] = ranks_df["name"].fillna("").astype(str)
    ranks_df["title_norm"] = ranks_df["name"].map(normalize_text)
    ranks_df["title_key"] = ranks_df["name"].map(
        lambda value: normalize_text(value, alnum_only=True)
    )

    first_df = pd.read_csv(first_publishers_path)
    first_df = first_df.rename(
        columns={"id": "game_id", "publisher": "first_publisher"}
    )
    first_df["game_id"] = pd.to_numeric(first_df["game_id"], errors="coerce")
    first_df = first_df.dropna(subset=["game_id"])
    first_df["game_id"] = first_df["game_id"].astype("int64")
    first_df["first_publisher_norm"] = first_df["first_publisher"].map(
        clean_raw_publisher
    )
    first_lookup = first_df[["game_id", "first_publisher_norm"]].drop_duplicates(
        "game_id"
    )

    ranks_df = ranks_df.merge(
        first_lookup, left_on="id", right_on="game_id", how="left"
    )
    ranks_df = ranks_df.drop(columns=["game_id"])
    ranks_df["first_publisher_norm"] = ranks_df["first_publisher_norm"].fillna("")

    all_pub_df = pd.read_csv(
        all_publishers_path,
        sep="|",
        usecols=["game_id", "boardgamepublisher_name"],
        low_memory=False,
    )
    all_pub_df["game_id"] = pd.to_numeric(all_pub_df["game_id"], errors="coerce")
    all_pub_df = all_pub_df.dropna(subset=["game_id"])
    all_pub_df["game_id"] = all_pub_df["game_id"].astype("int64")
    all_pub_df["publisher_norm"] = all_pub_df["boardgamepublisher_name"].map(
        clean_raw_publisher
    )
    all_pub_df = all_pub_df[all_pub_df["publisher_norm"] != ""]

    publishers_by_game: dict[int, set[str]] = defaultdict(set)
    for row in all_pub_df.itertuples(index=False):
        publishers_by_game[int(row.game_id)].add(row.publisher_norm)

    versions_df = pd.read_csv(
        versions_path,
        sep="|",
        usecols=["game_id", "language", "version_nickname"],
        low_memory=False,
    )
    versions_df = versions_df[versions_df["language"].map(normalize_text).eq("english")]
    versions_df["game_id"] = pd.to_numeric(versions_df["game_id"], errors="coerce")
    versions_df = versions_df.dropna(subset=["game_id"])
    versions_df["game_id"] = versions_df["game_id"].astype("int64")
    versions_df["version_norm"] = versions_df["version_nickname"].map(normalize_text)
    versions_df = versions_df[versions_df["version_norm"] != ""]

    versions_by_game: dict[int, tuple[str, ...]] = {}
    for game_id, chunk in versions_df.groupby("game_id", sort=False):
        unique_versions = tuple(dict.fromkeys(chunk["version_norm"].tolist()))
        versions_by_game[int(game_id)] = unique_versions

    logger.info(
        "Loaded BGG data: %s games, %s publisher rows, %s version rows",
        len(ranks_df),
        len(all_pub_df),
        len(versions_df),
    )

    return ranks_df, publishers_by_game, versions_by_game


def evaluate_publisher_match(
    row_publisher: str,
    first_publisher: str,
    all_publishers: set[str],
    versions: tuple[str, ...],
    rules: MatchingRules,
) -> tuple[bool, str, float]:
    if not row_publisher:
        return False, "none", 0.0

    if rules.publisher_suffix_normalization_enabled:
        row_publisher_canonical = canonicalize_publisher(row_publisher)
        first_publisher_canonical = canonicalize_publisher(first_publisher)
        all_publishers_canonical = {
            canonicalize_publisher(publisher) for publisher in all_publishers
        }
        all_publishers_canonical.discard("")

        if (
            row_publisher_canonical
            and first_publisher_canonical
            and row_publisher_canonical == first_publisher_canonical
        ):
            return True, "first_exact", 100.0
        if (
            row_publisher_canonical
            and row_publisher_canonical in all_publishers_canonical
        ):
            return True, "any_exact", 95.0

    if row_publisher == first_publisher and first_publisher:
        return True, "first_exact", 100.0

    if row_publisher in all_publishers:
        return True, "any_exact", 95.0

    if first_publisher:
        fuzzy_first = fuzz.WRatio(row_publisher, first_publisher)
        if fuzzy_first >= 94:
            return True, "first_fuzzy", float(fuzzy_first)

    best_pub_fuzzy = 0
    for publisher in all_publishers:
        best_pub_fuzzy = max(best_pub_fuzzy, fuzz.WRatio(row_publisher, publisher))
    if best_pub_fuzzy >= 94:
        return True, "any_fuzzy", float(best_pub_fuzzy)

    if len(row_publisher) >= 5:
        for nickname in versions:
            if row_publisher in nickname:
                return True, "version_contains", 84.0

    best_version_fuzzy = 0
    for nickname in versions:
        best_version_fuzzy = max(
            best_version_fuzzy, fuzz.partial_ratio(row_publisher, nickname)
        )
    if best_version_fuzzy >= 96:
        return True, "version_fuzzy", float(best_version_fuzzy)

    return False, "none", 0.0


def confidence_from_top_candidates(
    top1: CandidateScore,
    top2: CandidateScore | None,
    *,
    forced_reason: str | None,
) -> str:
    if forced_reason is not None:
        return "manual"

    margin = top1.score - top2.score if top2 is not None else 9999.0
    if top1.dimension_count >= 3 and top1.title_score >= 90 and margin >= 60:
        return "high"
    if top1.dimension_count >= 2 and top1.title_score >= 86 and margin >= 40:
        return "medium"
    return "low"


def build_title_indexes(
    games_df: pd.DataFrame,
) -> tuple[dict[str, set[int]], dict[str, set[int]], dict[str, set[str]], list[str]]:
    ids_by_title_norm: dict[str, set[int]] = defaultdict(set)
    ids_by_title_key: dict[str, set[int]] = defaultdict(set)

    for row in games_df[["id", "title_norm", "title_key"]].itertuples(index=False):
        game_id = int(row.id)
        if row.title_norm:
            ids_by_title_norm[row.title_norm].add(game_id)
        if row.title_key:
            ids_by_title_key[row.title_key].add(game_id)

    fuzzy_titles = sorted(ids_by_title_norm.keys())
    fuzzy_by_first_char: dict[str, set[str]] = defaultdict(set)
    for title_norm in fuzzy_titles:
        first_char = title_norm[0] if title_norm else "#"
        fuzzy_by_first_char[first_char].add(title_norm)

    return ids_by_title_norm, ids_by_title_key, fuzzy_by_first_char, fuzzy_titles


def build_first_publisher_index(games_df: pd.DataFrame) -> dict[str, list[int]]:
    publisher_index: dict[str, list[int]] = {}
    grouped = games_df.groupby("first_publisher_norm", dropna=False, sort=False)
    for publisher_norm, chunk in grouped:
        key = str(publisher_norm or "")
        if not key:
            continue
        sorted_ids = (
            chunk.sort_values(["usersrated", "id"], ascending=[False, True])["id"]
            .astype("int64")
            .tolist()
        )
        publisher_index[key] = sorted_ids
    return publisher_index


def score_candidate(
    *,
    candidate_id: int,
    row_title_norm: str,
    row_title_key: str,
    row_publisher_norm: str,
    row_game_year: int | None,
    row_bgg_id: int | None,
    games_lookup: dict[int, dict[str, Any]],
    publishers_by_game: dict[int, set[str]],
    versions_by_game: dict[int, tuple[str, ...]],
    title_priors: set[int],
    forced_title_fix: int | None,
    forced_bgg_fix: int | None,
    rules: MatchingRules,
) -> CandidateScore:
    game = games_lookup[candidate_id]
    candidate_title_norm = game["title_norm"]
    candidate_title_key = game["title_key"]

    title_fuzzy = (
        float(fuzz.WRatio(row_title_norm, candidate_title_norm))
        if row_title_norm and candidate_title_norm
        else 0.0
    )
    title_exact = bool(row_title_norm and row_title_norm == candidate_title_norm)
    title_key_exact = bool(row_title_key and row_title_key == candidate_title_key)
    title_partial = bool(
        row_title_norm
        and candidate_title_norm
        and (
            row_title_norm in candidate_title_norm
            or candidate_title_norm in row_title_norm
        )
    )
    title_match = (
        title_exact
        or title_key_exact
        or title_fuzzy >= 88
        or (title_partial and title_fuzzy >= 80)
    )
    title_score = max(
        title_fuzzy, 100.0 if title_exact else 0.0, 98.0 if title_key_exact else 0.0
    )

    publisher_match, publisher_match_type, publisher_score = evaluate_publisher_match(
        row_publisher_norm,
        str(game.get("first_publisher_norm", "")),
        publishers_by_game.get(candidate_id, set()),
        versions_by_game.get(candidate_id, tuple()),
        rules,
    )

    candidate_year_raw = game.get("yearpublished")
    candidate_year = int(candidate_year_raw) if pd.notna(candidate_year_raw) else None
    year_match = (
        row_game_year is not None
        and candidate_year is not None
        and row_game_year + 1 >= candidate_year
    )

    id_match = row_bgg_id is not None and row_bgg_id == candidate_id

    pax_prior = candidate_id in title_priors
    manual_title_fix = forced_title_fix == candidate_id
    manual_bgg_fix = forced_bgg_fix == candidate_id
    is_expansion = bool(game.get("is_expansion_flag", 0))
    has_promo = has_promo_word(game.get("name", ""))

    dimension_count = (
        int(title_match) + int(publisher_match) + int(year_match) + int(id_match)
    )
    usersrated_raw = game.get("usersrated")
    usersrated = int(usersrated_raw) if pd.notna(usersrated_raw) else None
    popularity_override = (
        rules.popularity_override_enabled
        and usersrated is not None
        and usersrated >= rules.popularity_override_min_usersrated
        and title_score >= rules.popularity_override_min_title_score
    )

    score = 0.0
    score += dimension_count * 1000.0
    score += title_score * 2.0
    if (
        title_exact
        and not is_expansion
        and not has_promo
        and len(ALNUM_TOKEN_PATTERN.findall(row_title_norm)) >= 2
    ):
        score += TITLE_EXACT_MATCH_BONUS
    score += publisher_score
    if title_exact and publisher_match_type == "first_exact":
        score += TITLE_FIRST_PUBLISHER_EXACT_BONUS
    score += 30.0 if year_match else 0.0
    score += 20.0 if id_match else 0.0
    score += min(float(usersrated or 0), 200000.0) / 1000.0
    score += 4000.0 if pax_prior else 0.0
    score += 25000.0 if manual_bgg_fix else 0.0
    score += 50000.0 if manual_title_fix else 0.0
    score -= EXPANSION_SCORE_PENALTY if is_expansion else 0.0
    score -= PROMO_SCORE_PENALTY if has_promo else 0.0
    if (
        rules.year_gap_penalty_enabled
        and not popularity_override
        and row_game_year is not None
        and candidate_year is not None
    ):
        year_gap = abs(row_game_year - candidate_year)
        if year_gap > rules.year_gap_hard_threshold:
            score -= rules.year_gap_hard_penalty
        elif year_gap > rules.year_gap_soft_threshold:
            score -= rules.year_gap_soft_penalty
    if rules.subtitle_penalty_enabled and should_apply_subtitle_penalty(
        row_title_norm=row_title_norm,
        candidate_title_norm=candidate_title_norm,
    ):
        score -= rules.subtitle_miss_penalty
    if (
        rules.generic_title_guard_enabled
        and not popularity_override
        and is_generic_title(row_title_norm, rules)
    ):
        if not publisher_match:
            score -= rules.generic_title_without_publisher_penalty
        if not year_match:
            score -= rules.generic_title_without_year_penalty

    return CandidateScore(
        bgg_id=candidate_id,
        bgg_name=str(game["name"]),
        score=score,
        dimension_count=dimension_count,
        title_score=title_score,
        title_match=title_match,
        publisher_match=publisher_match,
        publisher_match_type=publisher_match_type,
        year_match=year_match,
        id_match=id_match,
        yearpublished=candidate_year,
        usersrated=usersrated,
        pax_prior=pax_prior,
        manual_title_fix=manual_title_fix,
        manual_bgg_fix=manual_bgg_fix,
        is_expansion=is_expansion,
        has_promo_word=has_promo,
    )


def rank_candidates(candidates: list[CandidateScore]) -> list[CandidateScore]:
    """Sort candidates deterministically after applying the primary score."""

    return sorted(
        candidates,
        key=lambda candidate: (
            candidate.score,
            candidate.title_score,
            candidate.dimension_count,
            candidate.usersrated or 0,
            -candidate.bgg_id,
        ),
        reverse=True,
    )
