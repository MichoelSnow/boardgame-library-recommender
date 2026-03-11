import logging
from pathlib import Path
import threading
import time
from typing import List, Optional
from sqlalchemy import exists
from sqlalchemy.orm import Session
from . import models
import numpy as np
from scipy import sparse
from sklearn.preprocessing import normalize
import json
import os

logger = logging.getLogger(__name__)

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


class ModelManager:
    _instance = None
    _instance_lock = threading.Lock()
    _load_lock = threading.Lock()
    _game_embeddings = None
    _model_path = None
    _game_mapping = {}  # Maps game IDs to indices
    _reverse_game_mapping = {}  # Maps indices back to game IDs
    _last_load_error = None

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
                game_embeddings_files = list(database_dir.glob("game_embeddings_*.npz"))
                reverse_mappings_files = list(
                    database_dir.glob("reverse_mappings_*.json")
                )

                if not game_embeddings_files:
                    raise FileNotFoundError("No embeddings files found")
                if not reverse_mappings_files:
                    raise FileNotFoundError("No reverse mapping files found")

                reverse_mappings_by_timestamp = {}
                for mapping_file in reverse_mappings_files:
                    timestamp = self._extract_timestamp_int(
                        mapping_file, "reverse_mappings"
                    )
                    if timestamp is not None:
                        reverse_mappings_by_timestamp[timestamp] = mapping_file

                matched_pairs = []
                for embeddings_file in game_embeddings_files:
                    timestamp = self._extract_timestamp_int(
                        embeddings_file, "game_embeddings"
                    )
                    if timestamp is None:
                        continue
                    mapping_file = reverse_mappings_by_timestamp.get(timestamp)
                    if mapping_file:
                        matched_pairs.append((timestamp, embeddings_file, mapping_file))

                if not matched_pairs:
                    raise FileNotFoundError(
                        "No matched embeddings/reverse mapping artifact pairs found"
                    )

                _, latest_game_embeddings, latest_reverse_mappings = max(
                    matched_pairs,
                    key=lambda pair: pair[0],
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

    def get_model(self):
        """Get the current embeddings, loading them if necessary."""
        if self._game_embeddings is None:
            self.load_model()
        if self._game_embeddings is None:
            raise RuntimeError("Recommendation embeddings are unavailable")
        return self._game_embeddings

    def get_status(self):
        """Return whether recommendation artifacts are currently available."""
        if self._game_embeddings is not None:
            return {
                "available": True,
                "state": "available",
                "detail": None,
            }

        detail = self._last_load_error or "Recommendation model not loaded"
        return {
            "available": False,
            "state": "degraded",
            "detail": detail,
        }


def get_recommendations(
    db: Session,
    limit: int = 20,
    liked_games: Optional[List[int]] = None,
    disliked_games: Optional[List[int]] = None,
    anti_weight: float = 1.0,
    pax_only: Optional[bool] = False,
) -> List[dict[str, object]]:
    """
    Get game recommendations using the game embeddings.

    Args:
        db: Database session
        limit: Maximum number of recommendations to return
        liked_games: Optional list of game IDs to use as positive recommendations
        disliked_games: Optional list of game IDs to use as anti-recommendations
        anti_weight: Weight to apply to anti-recommendations
        pax_only: If true, only recommend games that are in the PAX games table

    Returns:
        List of recommended game payloads
    """
    try:
        started_total = time.perf_counter()
        timing: dict[str, float] = {}

        stage_started = time.perf_counter()
        model_manager = ModelManager.get_instance()
        game_embeddings = model_manager.get_model()
        game_mapping = model_manager._game_mapping
        reverse_game_mapping = model_manager._reverse_game_mapping
        timing["model_load_ms"] = (time.perf_counter() - stage_started) * 1000

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
        if pax_only:
            game_query = game_query.filter(
                exists().where(models.PAXGame.bgg_id == models.BoardGame.id)
            )

        game_map: dict[int, dict[str, object]] = {}
        for row in game_query.all():
            row_data = dict(zip(BOARD_GAME_COLUMN_NAMES, row))
            game_map[row_data["id"]] = row_data
        timing["db_fetch_ms"] = (time.perf_counter() - stage_started) * 1000

        stage_started = time.perf_counter()

        # Build the final list, sorted by score
        result_games: list[dict[str, object]] = []
        for game_id, score in recommended_games_with_scores:
            if game_id in game_map:
                result_games.append(
                    build_recommendation_payload(game_map[game_id], float(score))
                )
            if len(result_games) >= limit:
                break

        # Sort by recommendation score before returning
        def _score_value(item: dict[str, object]) -> float:
            raw_value = item.get("recommendation_score", 0.0)
            if isinstance(raw_value, (int, float)):
                return float(raw_value)
            return 0.0

        result_games.sort(key=_score_value, reverse=True)
        timing["result_assembly_ms"] = (time.perf_counter() - stage_started) * 1000
        total_ms = (time.perf_counter() - started_total) * 1000

        # Per-stage timing instrumentation for load/performance analysis.
        logger.info(
            "Recommendation timing ms total=%.1f model=%.1f map=%.1f query=%.1f score=%.1f "
            "exclude=%.1f topk=%.1f materialize=%.1f db=%.1f assemble=%.1f liked=%d disliked=%d result=%d",
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
            len(liked_indices),
            len(disliked_indices),
            len(result_games),
        )

        return result_games

    except Exception as e:
        logger.error(f"Error getting recommendations: {str(e)}", exc_info=True)
        return []
