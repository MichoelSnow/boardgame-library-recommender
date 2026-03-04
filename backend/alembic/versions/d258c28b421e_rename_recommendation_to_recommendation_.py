"""rename recommendation to recommendation_level

Revision ID: d258c28b421e
Revises: 
Create Date: 2025-06-08 21:16:26.277120

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd258c28b421e'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _bootstrap_base_schema() -> None:
    op.create_table(
        "games",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("thumbnail", sa.String(), nullable=True),
        sa.Column("image", sa.String(), nullable=True),
        sa.Column("min_players", sa.Integer(), nullable=True),
        sa.Column("max_players", sa.Integer(), nullable=True),
        sa.Column("playing_time", sa.Integer(), nullable=True),
        sa.Column("min_playtime", sa.Integer(), nullable=True),
        sa.Column("max_playtime", sa.Integer(), nullable=True),
        sa.Column("min_age", sa.Integer(), nullable=True),
        sa.Column("year_published", sa.Integer(), nullable=True),
        sa.Column("average", sa.Float(), nullable=True),
        sa.Column("num_ratings", sa.Integer(), nullable=True),
        sa.Column("num_comments", sa.Integer(), nullable=True),
        sa.Column("num_weights", sa.Integer(), nullable=True),
        sa.Column("average_weight", sa.Float(), nullable=True),
        sa.Column("stddev", sa.Float(), nullable=True),
        sa.Column("median", sa.Float(), nullable=True),
        sa.Column("owned", sa.Integer(), nullable=True),
        sa.Column("trading", sa.Integer(), nullable=True),
        sa.Column("wanting", sa.Integer(), nullable=True),
        sa.Column("wishing", sa.Integer(), nullable=True),
        sa.Column("bayes_average", sa.Float(), nullable=True),
        sa.Column("users_rated", sa.Integer(), nullable=True),
        sa.Column("is_expansion", sa.Boolean(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("abstracts_rank", sa.Integer(), nullable=True),
        sa.Column("cgs_rank", sa.Integer(), nullable=True),
        sa.Column("childrens_games_rank", sa.Integer(), nullable=True),
        sa.Column("family_games_rank", sa.Integer(), nullable=True),
        sa.Column("party_games_rank", sa.Integer(), nullable=True),
        sa.Column("strategy_games_rank", sa.Integer(), nullable=True),
        sa.Column("thematic_rank", sa.Integer(), nullable=True),
        sa.Column("wargames_rank", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    for table_name, name_id_column, name_column in (
        ("mechanics", "boardgamemechanic_id", "boardgamemechanic_name"),
        ("categories", "boardgamecategory_id", "boardgamecategory_name"),
        ("designers", "boardgamedesigner_id", "boardgamedesigner_name"),
        ("artists", "boardgameartist_id", "boardgameartist_name"),
        ("publishers", "boardgamepublisher_id", "boardgamepublisher_name"),
    ):
        op.create_table(
            table_name,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("game_id", sa.Integer(), nullable=True),
            sa.Column(name_id_column, sa.Integer(), nullable=True),
            sa.Column(name_column, sa.String(), nullable=True),
            sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    op.create_table(
        "suggested_players",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=True),
        sa.Column("player_count", sa.Integer(), nullable=True),
        sa.Column("best", sa.Integer(), nullable=True),
        sa.Column("recommended", sa.Integer(), nullable=True),
        sa.Column("not_recommended", sa.Integer(), nullable=True),
        sa.Column("game_total_votes", sa.Integer(), nullable=True),
        sa.Column("player_count_total_votes", sa.Integer(), nullable=True),
        sa.Column("recommendation_level", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "language_dependence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=True),
        sa.Column("level_1", sa.Integer(), nullable=True),
        sa.Column("level_2", sa.Integer(), nullable=True),
        sa.Column("level_3", sa.Integer(), nullable=True),
        sa.Column("level_4", sa.Integer(), nullable=True),
        sa.Column("level_5", sa.Integer(), nullable=True),
        sa.Column("total_votes", sa.Integer(), nullable=True),
        sa.Column("language_dependency", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    for table_name, id_column, name_column in (
        ("integrations", "boardgameintegration_id", "boardgameintegration_name"),
        ("implementations", "boardgameimplementation_id", "boardgameimplementation_name"),
        ("compilations", "boardgamecompilation_id", "boardgamecompilation_name"),
        ("expansions", "boardgameexpansion_id", "boardgameexpansion_name"),
        ("families", "boardgamefamily_id", "boardgamefamily_name"),
    ):
        op.create_table(
            table_name,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("game_id", sa.Integer(), nullable=True),
            sa.Column(id_column, sa.Integer(), nullable=True),
            sa.Column(name_column, sa.String(), nullable=True),
            sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    op.create_table(
        "versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=True),
        sa.Column("version_id", sa.Integer(), nullable=True),
        sa.Column("width", sa.Float(), nullable=True),
        sa.Column("length", sa.Float(), nullable=True),
        sa.Column("depth", sa.Float(), nullable=True),
        sa.Column("year_published", sa.Integer(), nullable=True),
        sa.Column("thumbnail", sa.String(), nullable=True),
        sa.Column("image", sa.String(), nullable=True),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("version_nickname", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "pax_games",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("name_raw", sa.String(), nullable=True),
        sa.Column("bgg_id", sa.Integer(), nullable=True),
        sa.Column("publisher", sa.String(), nullable=True),
        sa.Column("min_titles_id", sa.Integer(), nullable=True),
        sa.Column("titles_id_list", sa.String(), nullable=True),
        sa.Column("convention_name", sa.String(), nullable=True),
        sa.Column("convention_year", sa.Integer(), nullable=True),
        sa.Column("year_title_first_added", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["bgg_id"], ["games.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    for table_name in ("user_liked_games", "user_disliked_games"):
        op.create_table(
            table_name,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("game_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f(f"ix_{table_name}_id"), table_name, ["id"], unique=False)

    for index_name, columns in (
        ("idx_games_rank", ["rank"]),
        ("idx_games_average", ["average"]),
        ("idx_games_average_weight", ["average_weight"]),
        ("idx_games_year_published", ["year_published"]),
        ("idx_games_abstracts_rank", ["abstracts_rank"]),
        ("idx_games_cgs_rank", ["cgs_rank"]),
        ("idx_games_childrens_games_rank", ["childrens_games_rank"]),
        ("idx_games_family_games_rank", ["family_games_rank"]),
        ("idx_games_party_games_rank", ["party_games_rank"]),
        ("idx_games_strategy_games_rank", ["strategy_games_rank"]),
        ("idx_games_thematic_rank", ["thematic_rank"]),
        ("idx_games_wargames_rank", ["wargames_rank"]),
        ("idx_games_name", ["name"]),
        ("idx_games_min_players", ["min_players"]),
        ("idx_games_max_players", ["max_players"]),
    ):
        op.create_index(index_name, "games", columns, unique=False)

    for index_name, table_name, columns in (
        ("idx_mechanics_game_id", "mechanics", ["game_id"]),
        ("idx_mechanics_boardgamemechanic_id", "mechanics", ["boardgamemechanic_id"]),
        ("idx_categories_game_id", "categories", ["game_id"]),
        ("idx_categories_boardgamecategory_id", "categories", ["boardgamecategory_id"]),
        ("idx_designers_game_id", "designers", ["game_id"]),
        ("idx_designers_boardgamedesigner_id", "designers", ["boardgamedesigner_id"]),
        ("idx_artists_game_id", "artists", ["game_id"]),
        ("idx_artists_boardgameartist_id", "artists", ["boardgameartist_id"]),
        ("idx_suggested_players_game_id", "suggested_players", ["game_id"]),
        ("idx_suggested_players_player_count", "suggested_players", ["player_count"]),
        ("idx_suggested_players_recommendation_level", "suggested_players", ["recommendation_level"]),
        ("idx_pax_games_bgg_id", "pax_games", ["bgg_id"]),
    ):
        op.create_index(index_name, table_name, columns, unique=False)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "suggested_players" not in inspector.get_table_names():
        _bootstrap_base_schema()
        return

    suggested_player_columns = {
        column["name"] for column in inspector.get_columns("suggested_players")
    }
    if (
        "recommendation_level" not in suggested_player_columns
        and "recommendation" in suggested_player_columns
    ):
        op.add_column(
            "suggested_players",
            sa.Column("recommendation_level", sa.String(), nullable=True),
        )
        op.drop_column("suggested_players", "recommendation")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "suggested_players" not in inspector.get_table_names():
        return

    suggested_player_columns = {
        column["name"] for column in inspector.get_columns("suggested_players")
    }
    if (
        "recommendation" not in suggested_player_columns
        and "recommendation_level" in suggested_player_columns
    ):
        op.add_column(
            "suggested_players",
            sa.Column("recommendation", sa.VARCHAR(), nullable=True),
        )
        op.drop_column("suggested_players", "recommendation_level")
