import logging
from pathlib import Path
import threading
import time
from dataclasses import dataclass
from typing import List, Optional
from sqlalchemy.orm import Session
from . import models
import numpy as np
from scipy import sparse
from sklearn.preprocessing import normalize
import json
import os

logger = logging.getLogger(__name__)

RECOMMENDER_MODE_COLLABORATIVE = "collaborative"
RECOMMENDER_MODE_HYBRID = "hybrid"
SUPPORTED_RECOMMENDER_MODES = {
    RECOMMENDER_MODE_COLLABORATIVE,
    RECOMMENDER_MODE_HYBRID,
}


@dataclass(frozen=True)
class HybridScoringConfig:
    """Centralized hybrid scoring inputs.

    Keep these values in one place so we can later expose them via API/UI controls.
    """

    collaborative_weight: float = 0.50
    content_weight: float = 0.50
    quality_weight: float = 0.0
    quality_bayes_scale: float = 10.0
    quality_confidence_k: float = 1000.0
    quality_confidence_floor: float = 0.5
    quality_confidence_power: float = 1.0


HYBRID_SCORING_CONFIG = HybridScoringConfig()

BOARD_GAME_COLUMN_NAMES = tuple(
    column.name for column in models.BoardGame.__table__.columns
)
BOARD_GAME_SCALAR_COLUMNS = tuple(
    getattr(models.BoardGame, column_name) for column_name in BOARD_GAME_COLUMN_NAMES
)


def build_recommendation_payload(
    game_record: dict[str, object], score: float
) -> dict[str, object]:
    payload = dict(game_record)
    payload["recommendation_score"] = score
    return payload


def _normalize_zero_to_one(value: float, lower: float, upper: float) -> float:
    if upper <= lower:
        return 0.0
    return max(0.0, min(1.0, (value - lower) / (upper - lower)))


def _clamp_zero_to_one(value: float) -> float:
    return max(0.0, min(1.0, value))


def _compute_quality_score(
    *,
    bayes_value: float | None,
    num_ratings: int | None,
    config: HybridScoringConfig,
) -> float:
    bayes01 = 0.0
    if bayes_value is not None:
        bayes01 = _clamp_zero_to_one(float(bayes_value) / config.quality_bayes_scale)

    ratings_count = max(int(num_ratings or 0), 0)
    k = max(float(config.quality_confidence_k), 1.0)
    confidence = ratings_count / (ratings_count + k)
    confidence = _clamp_zero_to_one(confidence)
    confidence = confidence ** max(float(config.quality_confidence_power), 0.0)

    floor = _clamp_zero_to_one(float(config.quality_confidence_floor))
    confidence_adjustment = floor + (1.0 - floor) * confidence
    return _clamp_zero_to_one(bayes01 * confidence_adjustment)


def _normalized_hybrid_weights(
    config: HybridScoringConfig,
) -> tuple[float, float, float]:
    weights = np.asarray(
        [
            float(config.collaborative_weight),
            float(config.content_weight),
            float(config.quality_weight),
        ],
        dtype=float,
    )
    weights = np.maximum(weights, 0.0)
    total = float(weights.sum())
    if total <= 0.0:
        return (1.0, 0.0, 0.0)
    normalized = weights / total
    return (float(normalized[0]), float(normalized[1]), float(normalized[2]))


def _compute_embedding_similarity_scores(
    *,
    embeddings: sparse.csr_matrix,
    game_mapping: dict[int, int],
    source_game_ids: list[int],
    candidate_ids: list[int],
) -> dict[int, float]:
    source_indices = [
        game_mapping[game_id] for game_id in source_game_ids if game_id in game_mapping
    ]
    candidate_pairs = [
        (game_id, game_mapping[game_id])
        for game_id in candidate_ids
        if game_id in game_mapping
    ]
    if not source_indices or not candidate_pairs:
        return {}

    source_vec = embeddings[source_indices].mean(axis=0)
    source_vec = normalize(np.asarray(source_vec), norm="l2")
    if source_vec.size == 0:
        return {}

    candidate_indices = [pair[1] for pair in candidate_pairs]
    raw_scores = embeddings[candidate_indices] @ source_vec.T
    raw_scores = np.asarray(raw_scores).ravel()
    if raw_scores.size == 0:
        return {}

    raw_min = float(raw_scores.min())
    raw_max = float(raw_scores.max())
    return {
        game_id: _normalize_zero_to_one(float(raw_score), raw_min, raw_max)
        for (game_id, _), raw_score in zip(candidate_pairs, raw_scores)
    }


def _compute_hybrid_scores(
    *,
    recommended_games_with_scores: list[tuple[int, float]],
    game_map: dict[int, dict[str, object]],
    content_scores_by_game_id: dict[int, float],
    config: HybridScoringConfig = HYBRID_SCORING_CONFIG,
) -> dict[int, float]:
    candidate_ids = [
        game_id for game_id, _ in recommended_games_with_scores if game_id in game_map
    ]
    if not candidate_ids:
        return {}

    base_scores = [
        float(score)
        for game_id, score in recommended_games_with_scores
        if game_id in game_map
    ]
    base_min = min(base_scores)
    base_max = max(base_scores)
    base_norm_map = {
        game_id: _normalize_zero_to_one(float(score), base_min, base_max)
        for game_id, score in recommended_games_with_scores
        if game_id in game_map
    }

    collab_weight, content_weight, quality_weight = _normalized_hybrid_weights(config)

    hybrid_scores: dict[int, float] = {}
    for candidate_id in candidate_ids:
        game_row = game_map[candidate_id]
        content_score = content_scores_by_game_id.get(candidate_id, 0.0)

        bayes = game_row.get("bayes_average")
        if bayes is None:
            bayes = game_row.get("average")
        quality_score = _compute_quality_score(
            bayes_value=float(bayes) if bayes is not None else None,
            num_ratings=(
                int(game_row.get("num_ratings"))
                if game_row.get("num_ratings") is not None
                else None
            ),
            config=config,
        )

        collaborative_score = base_norm_map.get(candidate_id, 0.0)
        hybrid_scores[candidate_id] = (
            collab_weight * collaborative_score
            + content_weight * content_score
            + quality_weight * quality_score
        )

    return hybrid_scores


class ModelManager:
    _instance = None
    _instance_lock = threading.Lock()
    _load_lock = threading.Lock()
    _game_embeddings = None
    _model_path = None
    _game_mapping = {}  # Maps game IDs to indices
    _reverse_game_mapping = {}  # Maps indices back to game IDs
    _content_embeddings = None
    _content_model_path = None
    _content_game_mapping = {}  # Maps game IDs to indices
    _content_reverse_game_mapping = {}  # Maps indices back to game IDs
    _last_load_error = None
    _last_content_load_error = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @staticmethod
    def _extract_timestamp(file_path: Path, prefix: str) -> Optional[str]:
        stem = file_path.stem
        expected_prefix = f"{prefix}_"
        if not stem.startswith(expected_prefix):
            return None
        return stem[len(expected_prefix) :]

    @classmethod
    def _extract_timestamp_int(cls, file_path: Path, prefix: str) -> Optional[int]:
        timestamp = cls._extract_timestamp(file_path, prefix)
        if timestamp is None:
            return None
        try:
            return int(timestamp)
        except ValueError:
            return None

    @classmethod
    def _find_latest_artifact_pair(
        cls,
        *,
        database_dir: Path,
        embeddings_prefix: str,
        mapping_prefix: str,
    ) -> tuple[Path, Path]:
        embeddings_files = list(database_dir.glob(f"{embeddings_prefix}_*.npz"))
        mapping_files = list(database_dir.glob(f"{mapping_prefix}_*.json"))
        if not embeddings_files:
            raise FileNotFoundError(f"No {embeddings_prefix} files found")
        if not mapping_files:
            raise FileNotFoundError(f"No {mapping_prefix} files found")

        mappings_by_timestamp: dict[int, Path] = {}
        for mapping_file in mapping_files:
            timestamp = cls._extract_timestamp_int(mapping_file, mapping_prefix)
            if timestamp is not None:
                mappings_by_timestamp[timestamp] = mapping_file

        matched_pairs: list[tuple[int, Path, Path]] = []
        for embeddings_file in embeddings_files:
            timestamp = cls._extract_timestamp_int(embeddings_file, embeddings_prefix)
            if timestamp is None:
                continue
            mapping_file = mappings_by_timestamp.get(timestamp)
            if mapping_file is not None:
                matched_pairs.append((timestamp, embeddings_file, mapping_file))

        if not matched_pairs:
            raise FileNotFoundError(
                f"No matched {embeddings_prefix}/{mapping_prefix} artifact pairs found"
            )

        _, latest_embeddings, latest_mapping = max(
            matched_pairs, key=lambda pair: pair[0]
        )
        return latest_embeddings, latest_mapping

    def load_model(self):
        """Load the most recent game embeddings from the data directory."""
        if self._game_embeddings is not None:
            return self._game_embeddings
        with self._load_lock:
            if self._game_embeddings is not None:
                return self._game_embeddings
            try:
                # Use environment variable for database directory in production
                database_dir = Path(
                    os.getenv(
                        "DATABASE_DIR", str(Path(__file__).parent.parent / "database")
                    )
                )
                if not list(database_dir.glob("game_embeddings_*.npz")):
                    raise FileNotFoundError("No embeddings files found")
                if not list(database_dir.glob("reverse_mappings_*.json")):
                    raise FileNotFoundError("No reverse mapping files found")
                latest_game_embeddings, latest_reverse_mappings = (
                    self._find_latest_artifact_pair(
                        database_dir=database_dir,
                        embeddings_prefix="game_embeddings",
                        mapping_prefix="reverse_mappings",
                    )
                )
                logger.info(
                    "Loading embeddings from: %s with mapping: %s",
                    latest_game_embeddings,
                    latest_reverse_mappings,
                )

                # Load the embeddings
                self._game_embeddings = sparse.load_npz(latest_game_embeddings)
                self._model_path = latest_game_embeddings

                # Load game mappings from the corresponding reverse mappings file
                with open(latest_reverse_mappings, "r", encoding="utf-8") as f:
                    self._reverse_game_mapping = {
                        int(k): v for k, v in json.load(f).items()
                    }
                    self._game_mapping = {
                        v: k for k, v in self._reverse_game_mapping.items()
                    }

                self._last_load_error = None
                return self._game_embeddings
            except Exception as exc:
                self._game_embeddings = None
                self._model_path = None
                self._game_mapping = {}
                self._reverse_game_mapping = {}
                self._last_load_error = str(exc)
                raise

    def load_content_model(self):
        """Load the most recent content embeddings from the data directory."""
        if self._content_embeddings is not None:
            return self._content_embeddings
        with self._load_lock:
            if self._content_embeddings is not None:
                return self._content_embeddings
            try:
                database_dir = Path(
                    os.getenv(
                        "DATABASE_DIR", str(Path(__file__).parent.parent / "database")
                    )
                )
                latest_content_embeddings, latest_content_mappings = (
                    self._find_latest_artifact_pair(
                        database_dir=database_dir,
                        embeddings_prefix="content_embeddings",
                        mapping_prefix="content_reverse_mappings",
                    )
                )
                logger.info(
                    "Loading content embeddings from: %s with mapping: %s",
                    latest_content_embeddings,
                    latest_content_mappings,
                )

                self._content_embeddings = sparse.load_npz(latest_content_embeddings)
                self._content_model_path = latest_content_embeddings
                with open(latest_content_mappings, "r", encoding="utf-8") as f:
                    self._content_reverse_game_mapping = {
                        int(k): v for k, v in json.load(f).items()
                    }
                    self._content_game_mapping = {
                        v: k for k, v in self._content_reverse_game_mapping.items()
                    }
                self._last_content_load_error = None
                return self._content_embeddings
            except Exception as exc:
                self._content_embeddings = None
                self._content_model_path = None
                self._content_game_mapping = {}
                self._content_reverse_game_mapping = {}
                self._last_content_load_error = str(exc)
                raise

    def get_model(self):
        """Get the current embeddings, loading them if necessary."""
        if self._game_embeddings is None:
            self.load_model()
        return self._game_embeddings

    def get_content_model(self):
        """Get the content embeddings, loading them if necessary."""
        if self._content_embeddings is None:
            self.load_content_model()
        return self._content_embeddings

    def get_status(self):
        """Return recommendation artifact readiness for collaborative and hybrid paths."""
        collaborative_available = self._game_embeddings is not None
        content_available = self._content_embeddings is not None
        detail = self._last_load_error or "Recommendation model not loaded"
        content_detail = (
            self._last_content_load_error
            if self._last_content_load_error is not None
            else (
                None
                if content_available
                else "Content embeddings not loaded; hybrid content rerank unavailable"
            )
        )

        if collaborative_available:
            detail = None

        return {
            "available": collaborative_available,
            "state": "available" if collaborative_available else "degraded",
            "detail": detail,
            "collaborative_available": collaborative_available,
            "content_available": content_available,
            "hybrid_available": collaborative_available and content_available,
            "content_detail": content_detail,
        }


def get_recommendations(
    db: Session,
    limit: int = 20,
    liked_games: Optional[List[int]] = None,
    disliked_games: Optional[List[int]] = None,
    anti_weight: float = 1.0,
    library_only: Optional[bool] = False,
    recommender_mode: str = RECOMMENDER_MODE_HYBRID,
    collaborative_weight: float | None = None,
    content_weight: float | None = None,
    quality_weight: float | None = None,
) -> List[dict[str, object]]:
    """
    Get game recommendations using the game embeddings.

    Args:
        db: Database session
        limit: Maximum number of recommendations to return
        liked_games: Optional list of game IDs to use as positive recommendations
        disliked_games: Optional list of game IDs to use as anti-recommendations
        anti_weight: Weight to apply to anti-recommendations
        library_only: If true, only recommend games from the active library import
        recommender_mode: 'collaborative' (cosine only) or 'hybrid' (collab + content + quality rerank)

    Returns:
        List of recommended game payloads
    """
    try:
        started_total = time.perf_counter()
        timing: dict[str, float] = {}
        config = HybridScoringConfig(
            collaborative_weight=(
                collaborative_weight
                if collaborative_weight is not None
                else HYBRID_SCORING_CONFIG.collaborative_weight
            ),
            content_weight=(
                content_weight
                if content_weight is not None
                else HYBRID_SCORING_CONFIG.content_weight
            ),
            quality_weight=(
                quality_weight
                if quality_weight is not None
                else HYBRID_SCORING_CONFIG.quality_weight
            ),
            quality_bayes_scale=HYBRID_SCORING_CONFIG.quality_bayes_scale,
            quality_confidence_k=HYBRID_SCORING_CONFIG.quality_confidence_k,
            quality_confidence_floor=HYBRID_SCORING_CONFIG.quality_confidence_floor,
            quality_confidence_power=HYBRID_SCORING_CONFIG.quality_confidence_power,
        )

        stage_started = time.perf_counter()
        model_manager = ModelManager.get_instance()
        game_embeddings = model_manager.get_model()
        game_mapping = model_manager._game_mapping
        reverse_game_mapping = model_manager._reverse_game_mapping
        content_embeddings = None
        content_game_mapping: dict[int, int] = {}
        if recommender_mode == RECOMMENDER_MODE_HYBRID:
            try:
                content_embeddings = model_manager.get_content_model()
                content_game_mapping = model_manager._content_game_mapping
            except Exception as exc:
                logger.warning(
                    "Hybrid content embeddings unavailable; falling back to collaborative+quality scoring: %s",
                    exc,
                )
        timing["model_load_ms"] = (time.perf_counter() - stage_started) * 1000

        if recommender_mode not in SUPPORTED_RECOMMENDER_MODES:
            raise ValueError(
                f"Unsupported recommender_mode='{recommender_mode}'. "
                f"Supported values: {sorted(SUPPORTED_RECOMMENDER_MODES)}"
            )

        if not liked_games and not disliked_games:
            return []

        stage_started = time.perf_counter()
        liked_indices = (
            [game_mapping[g_id] for g_id in liked_games if g_id in game_mapping]
            if liked_games
            else []
        )
        disliked_indices = (
            [game_mapping[dg_id] for dg_id in disliked_games if dg_id in game_mapping]
            if disliked_games
            else []
        )
        timing["mapping_ms"] = (time.perf_counter() - stage_started) * 1000

        if not liked_indices and not disliked_indices:
            logger.warning(
                "None of the provided liked/disliked games were found in embeddings."
            )
            return []

        # Compute mean of liked and disliked games
        stage_started = time.perf_counter()
        pos_vec = game_embeddings[liked_indices].mean(axis=0) if liked_indices else 0
        neg_vec = (
            game_embeddings[disliked_indices].mean(axis=0) if disliked_indices else 0
        )

        query_vec = pos_vec - anti_weight * neg_vec

        if isinstance(query_vec, int):
            return []

        query_vec = normalize(np.asarray(query_vec), norm="l2")
        timing["query_vector_ms"] = (time.perf_counter() - stage_started) * 1000

        # Compute cosine similarity between query vector and all game embeddings
        stage_started = time.perf_counter()
        scores = game_embeddings @ query_vec.T
        scores = np.asarray(scores).ravel()
        timing["scoring_ms"] = (time.perf_counter() - stage_started) * 1000

        # Zero out scores for input items
        stage_started = time.perf_counter()
        excluded_indices = np.unique(
            np.asarray(liked_indices + disliked_indices, dtype=int)
        )
        if excluded_indices.size > 0:
            scores[excluded_indices] = -1
        timing["exclude_inputs_ms"] = (time.perf_counter() - stage_started) * 1000

        # Get top N similar games without sorting all scores.
        # Fetch more than limit to account for games not in DB/filtering losses.
        stage_started = time.perf_counter()
        candidate_count = min(max(limit * 4, 50), scores.shape[0])
        if candidate_count >= scores.shape[0]:
            top_indices = np.argsort(scores)[::-1]
        else:
            partition_start = scores.shape[0] - candidate_count
            candidate_indices = np.argpartition(scores, partition_start)[
                partition_start:
            ]
            top_indices = candidate_indices[np.argsort(scores[candidate_indices])[::-1]]
        timing["topk_selection_ms"] = (time.perf_counter() - stage_started) * 1000

        stage_started = time.perf_counter()
        recommended_games_with_scores = []
        for idx in top_indices:
            if scores[idx] > 0:
                recommended_games_with_scores.append(
                    (int(reverse_game_mapping[idx]), scores[idx])
                )
        timing["candidate_materialization_ms"] = (
            time.perf_counter() - stage_started
        ) * 1000

        recommended_ids = [game[0] for game in recommended_games_with_scores]

        stage_started = time.perf_counter()
        # Fetch scalar columns only to avoid relationship loading/serialization overhead.
        game_query = db.query(*BOARD_GAME_SCALAR_COLUMNS).filter(
            models.BoardGame.id.in_(recommended_ids)
        )
        if library_only:
            from . import crud

            game_query = game_query.filter(crud.build_runtime_library_only_filter(db))

        game_map: dict[int, dict[str, object]] = {}
        for row in game_query.all():
            row_data = dict(zip(BOARD_GAME_COLUMN_NAMES, row))
            game_map[row_data["id"]] = row_data
        timing["db_fetch_ms"] = (time.perf_counter() - stage_started) * 1000

        stage_started = time.perf_counter()

        score_by_game_id = {
            game_id: float(score)
            for game_id, score in recommended_games_with_scores
            if game_id in game_map
        }
        if recommender_mode == RECOMMENDER_MODE_HYBRID and liked_games:
            content_scores_by_game_id = {}
            if content_embeddings is not None:
                content_scores_by_game_id = _compute_embedding_similarity_scores(
                    embeddings=content_embeddings,
                    game_mapping=content_game_mapping,
                    source_game_ids=[int(game_id) for game_id in liked_games],
                    candidate_ids=list(score_by_game_id.keys()),
                )
            score_by_game_id = _compute_hybrid_scores(
                recommended_games_with_scores=recommended_games_with_scores,
                game_map=game_map,
                content_scores_by_game_id=content_scores_by_game_id,
                config=config,
            )

        # Build the final list, sorted by score
        result_games: list[dict[str, object]] = []
        scored_game_ids = sorted(
            score_by_game_id.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        for game_id, score in scored_game_ids:
            if game_id in game_map:
                result_games.append(
                    build_recommendation_payload(game_map[game_id], float(score))
                )
            if len(result_games) >= limit:
                break

        # Sort by recommendation score before returning
        result_games.sort(
            key=lambda item: float(item.get("recommendation_score", 0.0)),
            reverse=True,
        )
        timing["result_assembly_ms"] = (time.perf_counter() - stage_started) * 1000
        total_ms = (time.perf_counter() - started_total) * 1000

        # Per-stage timing instrumentation for load/performance analysis.
        logger.info(
            "Recommendation timing ms total=%.1f model=%.1f map=%.1f query=%.1f score=%.1f "
            "exclude=%.1f topk=%.1f materialize=%.1f db=%.1f assemble=%.1f mode=%s liked=%d disliked=%d result=%d",
            total_ms,
            timing.get("model_load_ms", 0.0),
            timing.get("mapping_ms", 0.0),
            timing.get("query_vector_ms", 0.0),
            timing.get("scoring_ms", 0.0),
            timing.get("exclude_inputs_ms", 0.0),
            timing.get("topk_selection_ms", 0.0),
            timing.get("candidate_materialization_ms", 0.0),
            timing.get("db_fetch_ms", 0.0),
            timing.get("result_assembly_ms", 0.0),
            recommender_mode,
            len(liked_indices),
            len(disliked_indices),
            len(result_games),
        )

        return result_games

    except Exception as e:
        logger.error(f"Error getting recommendations: {str(e)}", exc_info=True)
        return []
