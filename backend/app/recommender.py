import logging
from pathlib import Path
from typing import List, Optional
from sqlalchemy.orm import Session
from . import models
import pandas as pd
import numpy as np
from scipy import sparse
from sklearn.preprocessing import normalize
import json
import os

logger = logging.getLogger(__name__)

class ModelManager:
    _instance = None
    _game_embeddings = None
    _model_path = None
    _game_mapping = {}  # Maps game IDs to indices
    _reverse_game_mapping = {}  # Maps indices back to game IDs

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_model(self):
        """Load the most recent game embeddings from the data directory."""
        if self._game_embeddings is not None:
            return self._game_embeddings

        # Use environment variable for database directory in production
        database_dir = Path(os.getenv("DATABASE_DIR", str(Path(__file__).parent.parent / "database")))
        game_embeddings_files = list(database_dir.glob("game_embeddings_*.npz"))
        reverse_mappings_files = list(database_dir.glob("reverse_mappings_*.json"))
        
        if not game_embeddings_files:
            raise FileNotFoundError("No embeddings files found")
        if not reverse_mappings_files:
            raise FileNotFoundError("No reverse mapping files found")

        latest_game_embeddings = max(game_embeddings_files, key=lambda x: x.stat().st_mtime)
        latest_reverse_mappings = max(reverse_mappings_files, key=lambda x: x.stat().st_mtime)
        logger.info(f"Loading embeddings from: {latest_game_embeddings}")

        # Load the embeddings
        self._game_embeddings = sparse.load_npz(latest_game_embeddings)
        self._model_path = latest_game_embeddings

        # Load game mappings from the corresponding reverse mappings file
        with open(latest_reverse_mappings, "r") as f:
            self._reverse_game_mapping = {int(k): v for k, v in json.load(f).items()} 
            self._game_mapping = {v: k for k, v in self._reverse_game_mapping.items()}

        return self._game_embeddings

    def get_model(self):
        """Get the current embeddings, loading them if necessary."""
        if self._game_embeddings is None:
            self.load_model()
        return self._game_embeddings

def get_recommendations(
    db: Session,
    limit: int = 20,
    liked_games: Optional[List[int]] = None,
    disliked_games: Optional[List[int]] = None,
    anti_weight: float = 1.0,
    pax_only: Optional[bool] = False
) -> List[models.BoardGame]:
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
        List of recommended BoardGame objects
    """
    try:
        model_manager = ModelManager.get_instance()
        game_embeddings = model_manager.get_model()
        game_mapping = model_manager._game_mapping
        reverse_game_mapping = model_manager._reverse_game_mapping
        
        if not liked_games and not disliked_games:
            return []
        
        liked_indices = [game_mapping[g_id] for g_id in liked_games if g_id in game_mapping] if liked_games else []
        disliked_indices = [game_mapping[dg_id] for dg_id in disliked_games if dg_id in game_mapping] if disliked_games else []
        
        if not liked_indices and not disliked_indices:
            logger.warning("None of the provided liked/disliked games were found in embeddings.")
            return []

        # Compute mean of liked and disliked games
        pos_vec = game_embeddings[liked_indices].mean(axis=0) if liked_indices else 0
        neg_vec = game_embeddings[disliked_indices].mean(axis=0) if disliked_indices else 0
        
        query_vec = pos_vec - anti_weight * neg_vec
        
        if isinstance(query_vec, int):
            return []

        query_vec = normalize(np.asarray(query_vec), norm='l2')

        # Compute cosine similarity between query vector and all game embeddings
        scores = game_embeddings @ query_vec.T
        scores = np.asarray(scores).ravel()

        # Zero out scores for input items
        for idx in liked_indices + disliked_indices:
            scores[idx] = -1
        
        # Get top N similar games
        # Fetch more than limit to account for games not in DB
        top_indices = np.argsort(scores)[-limit*2:][::-1]
        
        recommended_games_with_scores = []
        for idx in top_indices:
            if scores[idx] > 0:
                recommended_games_with_scores.append(
                    (int(reverse_game_mapping[idx]), scores[idx])
                )

        recommended_ids = [game[0] for game in recommended_games_with_scores]
        
        if pax_only:
            pax_game_ids = {pax.bgg_id for pax in db.query(models.PAXGame.bgg_id).filter(models.PAXGame.bgg_id.isnot(None)).all()}
            recommended_ids = [rid for rid in recommended_ids if rid in pax_game_ids]
            # Re-filter the scored list to match the id list
            recommended_games_with_scores = [game for game in recommended_games_with_scores if game[0] in recommended_ids]
        
        # Get full game objects from database
        games_from_db = db.query(models.BoardGame).filter(
            models.BoardGame.id.in_(recommended_ids)
        ).all()
        
        # Add score to game object and create a lookup
        game_map = {}
        for game in games_from_db:
            game_map[game.id] = game
        
        # Build the final list, sorted by score
        result_games = []
        for game_id, score in recommended_games_with_scores:
            if game_id in game_map:
                game = game_map[game_id]
                game.recommendation_score = score
                result_games.append(game)
            if len(result_games) >= limit:
                break
        
        # Sort by recommendation score before returning
        result_games.sort(key=lambda x: x.recommendation_score, reverse=True)

        return result_games
        
    except Exception as e:
        logger.error(f"Error getting recommendations: {str(e)}", exc_info=True)
        return []
