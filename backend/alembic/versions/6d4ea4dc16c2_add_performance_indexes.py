"""add_performance_indexes

Revision ID: 6d4ea4dc16c2
Revises: ed8c617c6e84
Create Date: 2025-07-12 11:32:49.889497

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6d4ea4dc16c2"
down_revision: Union[str, None] = "ed8c617c6e84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def create_index_if_missing(
    index_name: str, table_name: str, columns: list[str]
) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes = {index["name"] for index in inspector.get_indexes(table_name)}
    if index_name not in existing_indexes:
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    """Add critical performance indexes."""
    # Main games table indexes for sorting and filtering
    create_index_if_missing("ix_games_name", "games", ["name"])
    create_index_if_missing("ix_games_rank", "games", ["rank"])
    create_index_if_missing("ix_games_min_players", "games", ["min_players"])
    create_index_if_missing("ix_games_max_players", "games", ["max_players"])
    create_index_if_missing("ix_games_average_weight", "games", ["average_weight"])
    create_index_if_missing("ix_games_year_published", "games", ["year_published"])
    create_index_if_missing("ix_games_bayes_average", "games", ["bayes_average"])
    create_index_if_missing("ix_games_average", "games", ["average"])

    # All ranking columns for sorting
    create_index_if_missing("ix_games_abstracts_rank", "games", ["abstracts_rank"])
    create_index_if_missing("ix_games_cgs_rank", "games", ["cgs_rank"])
    create_index_if_missing(
        "ix_games_childrens_games_rank", "games", ["childrens_games_rank"]
    )
    create_index_if_missing(
        "ix_games_family_games_rank", "games", ["family_games_rank"]
    )
    create_index_if_missing("ix_games_party_games_rank", "games", ["party_games_rank"])
    create_index_if_missing(
        "ix_games_strategy_games_rank", "games", ["strategy_games_rank"]
    )
    create_index_if_missing("ix_games_thematic_rank", "games", ["thematic_rank"])
    create_index_if_missing("ix_games_wargames_rank", "games", ["wargames_rank"])

    # Player count range composite index for efficient player filtering
    create_index_if_missing(
        "ix_games_player_range", "games", ["min_players", "max_players"]
    )

    # Foreign key indexes for relationship tables
    create_index_if_missing("ix_mechanics_game_id", "mechanics", ["game_id"])
    create_index_if_missing(
        "ix_mechanics_boardgamemechanic_id", "mechanics", ["boardgamemechanic_id"]
    )
    create_index_if_missing("ix_categories_game_id", "categories", ["game_id"])
    create_index_if_missing(
        "ix_categories_boardgamecategory_id", "categories", ["boardgamecategory_id"]
    )
    create_index_if_missing("ix_designers_game_id", "designers", ["game_id"])
    create_index_if_missing(
        "ix_designers_boardgamedesigner_id", "designers", ["boardgamedesigner_id"]
    )
    create_index_if_missing("ix_artists_game_id", "artists", ["game_id"])
    create_index_if_missing(
        "ix_artists_boardgameartist_id", "artists", ["boardgameartist_id"]
    )
    create_index_if_missing("ix_publishers_game_id", "publishers", ["game_id"])
    create_index_if_missing(
        "ix_suggested_players_game_id", "suggested_players", ["game_id"]
    )
    create_index_if_missing(
        "ix_suggested_players_player_count", "suggested_players", ["player_count"]
    )
    create_index_if_missing(
        "ix_suggested_players_recommendation_level",
        "suggested_players",
        ["recommendation_level"],
    )

    # Library games index for library_only filtering
    create_index_if_missing("ix_library_games_bgg_id", "library_games", ["bgg_id"])

    # Composite indexes for common filter combinations
    create_index_if_missing(
        "ix_suggested_players_composite",
        "suggested_players",
        ["game_id", "player_count", "recommendation_level"],
    )
    create_index_if_missing(
        "ix_mechanics_composite", "mechanics", ["game_id", "boardgamemechanic_id"]
    )
    create_index_if_missing(
        "ix_categories_composite", "categories", ["game_id", "boardgamecategory_id"]
    )


def downgrade() -> None:
    """Remove performance indexes."""
    # Only drop indexes that were actually created
    try:
        # Drop composite indexes
        op.drop_index("ix_categories_composite", "categories")
        op.drop_index("ix_mechanics_composite", "mechanics")
        op.drop_index("ix_suggested_players_composite", "suggested_players")

        # Drop Library games index
        op.drop_index("ix_library_games_bgg_id", "library_games")

        # Drop relationship table indexes
        op.drop_index("ix_suggested_players_recommendation_level", "suggested_players")
        op.drop_index("ix_suggested_players_player_count", "suggested_players")
        op.drop_index("ix_suggested_players_game_id", "suggested_players")
        op.drop_index("ix_publishers_game_id", "publishers")
        op.drop_index("ix_artists_boardgameartist_id", "artists")
        op.drop_index("ix_artists_game_id", "artists")
        op.drop_index("ix_designers_boardgamedesigner_id", "designers")
        op.drop_index("ix_designers_game_id", "designers")
        op.drop_index("ix_categories_boardgamecategory_id", "categories")
        op.drop_index("ix_categories_game_id", "categories")
        op.drop_index("ix_mechanics_boardgamemechanic_id", "mechanics")
        op.drop_index("ix_mechanics_game_id", "mechanics")

        # Drop games table indexes that exist
        op.drop_index("ix_games_player_range", "games")
        op.drop_index("ix_games_average", "games")
        op.drop_index("ix_games_bayes_average", "games")
        op.drop_index("ix_games_year_published", "games")
        op.drop_index("ix_games_average_weight", "games")
        op.drop_index("ix_games_max_players", "games")
        op.drop_index("ix_games_min_players", "games")
        op.drop_index("ix_games_rank", "games")
    except Exception:
        # Some indexes may not exist, continue anyway
        pass
