import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.preprocessing import normalize
import argparse
import logging
from pathlib import Path
import json

try:
    from ..common.logging_utils import build_log_handlers
except ImportError:
    from data_pipeline.src.common.logging_utils import build_log_handlers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=build_log_handlers("recommender.log"),
)
logger = logging.getLogger(__name__)


class GameRecommender:
    def __init__(self, min_ratings_per_user: int = 3, exclude_expansions: bool = False):
        """
        Initialize the recommender system.

        Args:
            min_ratings_per_user (int): Minimum number of ratings a user must have to be included
            exclude_expansions (bool): Whether to exclude expansions from recommendations
        """
        self.min_ratings_per_user = min_ratings_per_user
        self.exclude_expansions = exclude_expansions
        self.user_mapping = {}  # Maps user IDs to indices
        self.game_mapping = {}  # Maps game IDs to indices
        self.reverse_game_mapping = {}  # Maps indices back to game IDs
        self.rating_matrix = None
        self.game_embeddings = None
        self.valid_game_ids = (
            None  # Set of valid game IDs (non-expansions if exclude_expansions is True)
        )

    def _create_rating_matrix(self, df: pd.DataFrame) -> sparse.csr_matrix:
        """
        Convert the input dataframe into a sparse rating matrix.

        Args:
            df (pd.DataFrame): Input dataframe with game_id as index and rating columns containing user lists

        Returns:
            sparse.csr_matrix: Sparse matrix of user-game ratings
        """
        # check if the dataframe has a column called "id"
        if "id" in df.columns:
            df = df.set_index("id")

        # Create mappings for users and games
        all_users = set()
        for col in df.columns:
            # Handle both list and non-list values in the ratings
            for users in df[col].dropna():
                if isinstance(users, list):
                    all_users.update(str(user) for user in users)
                else:
                    # If it's a single user, add them directly
                    all_users.add(str(users))

        # Create user mapping
        for i, user in enumerate(sorted(all_users)):
            self.user_mapping[user] = i

        # Create game mapping
        for i, game_id in enumerate(df.index):
            self.game_mapping[game_id] = i
            self.reverse_game_mapping[i] = game_id

        # Initialize sparse matrix
        n_users = len(self.user_mapping)
        n_games = len(self.game_mapping)
        rating_matrix = sparse.lil_matrix((n_users, n_games))

        # Fill the rating matrix
        for game_id, row in df.iterrows():
            game_idx = self.game_mapping[game_id]
            for rating, users in row.items():
                # Skip missing values.
                if users is None:
                    continue
                if not isinstance(users, list) and pd.isna(users):
                    continue

                # Normalize either list-valued users or scalar user values.
                iter_users = users if isinstance(users, list) else [users]

                # Add ratings for each user
                for user in iter_users:
                    user_id = str(user)
                    if user_id in self.user_mapping:
                        user_idx = self.user_mapping[user_id]
                        rating_matrix[user_idx, game_idx] = float(rating)

        # Convert to CSR format for efficient operations
        return rating_matrix.tocsr()

    def _filter_users(self, rating_matrix: sparse.csr_matrix) -> sparse.csr_matrix:
        """
        Remove users with fewer than min_ratings_per_user ratings.

        Args:
            rating_matrix (sparse.csr_matrix): Input rating matrix

        Returns:
            sparse.csr_matrix: Filtered rating matrix
        """
        # Count non-zero elements per user (number of ratings)
        user_rating_counts = np.diff(rating_matrix.indptr)

        # Get indices of users with enough ratings
        valid_user_indices = np.where(user_rating_counts >= self.min_ratings_per_user)[
            0
        ]

        # Filter the matrix
        return rating_matrix[valid_user_indices]

    def _load_valid_games(self):
        """Load the set of valid game IDs from the ranks file."""
        if not self.exclude_expansions:
            return None

        # Find the most recent ranks file
        ranks_dir = Path(__file__).resolve().parents[3] / "data" / "ingest" / "ranks"
        ranks_files = list(ranks_dir.glob("boardgame_ranks_*.csv"))
        if not ranks_files:
            logger.warning("No ranks files found, cannot exclude expansions")
            return None

        latest_ranks = max(ranks_files, key=lambda x: x.stat().st_mtime)
        logger.info(f"Loading valid games from: {latest_ranks}")

        # Read the ranks file and get non-expansion games
        df_ranks = pd.read_csv(latest_ranks, sep="|", escapechar="\\")
        valid_games = df_ranks[df_ranks["is_expansion"] == 0]["id"].tolist()
        return set(str(gid) for gid in valid_games)

    def fit(self, df: pd.DataFrame) -> None:
        """
        Fit the recommender system to the input data.

        Args:
            df (pd.DataFrame): Input dataframe with game_id as index and rating columns containing user lists
        """
        # Create and filter rating matrix
        self.rating_matrix = self._create_rating_matrix(df)
        self.rating_matrix = self._filter_users(self.rating_matrix)

        # Compute game similarity matrix
        self.game_embeddings = normalize(self.rating_matrix.T, norm="l2", axis=1)

    # def recommend_similar_games(
    #     self,
    #     game_ids: List[str],
    #     disliked_games: List[str] = None,
    #     n_recommendations: int = 5,
    #     anti_weight: float = 1.0,
    # ) -> List[Tuple[str, float]]:
    #     """
    #     Generate recommendations using vector arithmetic on item embeddings.
    #     """
    #     from sklearn.preprocessing import normalize

    #     # Convert liked/disliked game IDs to indices
    #     liked_indices = [
    #         self.game_mapping[g] for g in game_ids if g in self.game_mapping
    #     ]
    #     disliked_indices = [
    #         self.game_mapping[g] for g in disliked_games or [] if g in self.game_mapping
    #     ]

    #     if not liked_indices:
    #         return []

    #     # Get mean embedding vector
    #     pos_vec = self.game_embeddings[liked_indices].mean(axis=0)
    #     neg_vec = (
    #         self.game_embeddings[disliked_indices].mean(axis=0)
    #         if disliked_indices
    #         else 0
    #     )
    #     query_vec = pos_vec - anti_weight * neg_vec
    #     query_vec = normalize(query_vec, norm="l2")

    #     # Compute scores using sparse dot product
    #     scores = self.game_embeddings @ query_vec.T
    #     scores = np.array(scores.todense()).ravel()  # convert sparse to 1D dense array

    #     # Filter out input games
    #     for idx in liked_indices + disliked_indices:
    #         scores[idx] = -1

    #     # Exclude expansions if configured
    #     if self.exclude_expansions and self.valid_game_ids:
    #         for idx, game_id in self.reverse_game_mapping.items():
    #             if game_id not in self.valid_game_ids:
    #                 scores[idx] = -1

    #     # Return top N scores
    #     top_indices = np.argsort(scores)[-n_recommendations:][::-1]
    #     return [
    #         (self.reverse_game_mapping[idx], scores[idx])
    #         for idx in top_indices
    #         if scores[idx] > 0
    #     ]


def main():
    """Main function to train and save the recommender model."""
    try:
        parser = argparse.ArgumentParser(
            description="Train and save a the embeddings for a game recommender model"
        )
        parser.add_argument(
            "--min-ratings",
            type=int,
            default=3,
            help="Minimum number of ratings per user (default: 3)",
        )
        parser.add_argument(
            "--exclude-expansions",
            action="store_true",
            help="Exclude expansions from recommendations",
        )
        args = parser.parse_args()

        # Find the most recent ratings file
        ratings_dir = (
            Path(__file__).resolve().parents[3] / "data" / "ingest" / "ratings"
        )
        ratings_files = list(ratings_dir.glob("boardgame_ratings_*.parquet"))
        if not ratings_files:
            raise FileNotFoundError("No ratings files found")

        latest_ratings = max(ratings_files, key=lambda x: x.stat().st_mtime)
        logger.info(f"Using ratings file: {latest_ratings}")

        # Read ratings data
        df_ratings = pd.read_parquet(latest_ratings)

        # Initialize and train the recommender
        recommender = GameRecommender(
            min_ratings_per_user=args.min_ratings,
            exclude_expansions=args.exclude_expansions,
        )

        # Load valid games if excluding expansions
        if args.exclude_expansions:
            recommender.valid_game_ids = recommender._load_valid_games()

        recommender.fit(df_ratings)

        # Get timestamp from ratings file
        timestamp = latest_ratings.stem.split("_")[-1]

        # Save game embeddings as npz
        database_dir = Path(__file__).parent.parent.parent / "backend" / "database"
        embeddings_path = database_dir / f"game_embeddings_{timestamp}.npz"
        sparse.save_npz(
            file=embeddings_path,
            matrix=recommender.game_embeddings,
        )
        logger.info(f"Successfully saved embeddings to {embeddings_path}")

        # save reverse mappings as JSON
        reverse_mappings_path = database_dir / f"reverse_mappings_{timestamp}.json"
        with open(reverse_mappings_path, "w") as f:
            json.dump(recommender.reverse_game_mapping, f)
        logger.info(f"Successfully saved reverse mappings to {reverse_mappings_path}")

    except Exception as e:
        logger.error(f"Error training recommender model: {str(e)}")
        raise


if __name__ == "__main__":
    main()
