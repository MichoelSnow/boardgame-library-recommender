"""add_avg_box_volume_to_games

Revision ID: 4f77595d6dba
Revises: 7091f7e4de89
Create Date: 2025-08-15 09:40:47.350229

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4f77595d6dba"
down_revision: Union[str, None] = "7091f7e4de89"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {
        column["name"] for column in inspector.get_columns(table_name)
    }


def index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    # Add the avg_volume column to games table.
    if not column_exists("games", "avg_box_volume"):
        op.add_column("games", sa.Column("avg_box_volume", sa.Integer(), nullable=True))

    # Execute SQL to calculate and populate the avg_volume values
    op.execute("""
    UPDATE games
    SET avg_box_volume = (
        WITH vol AS (
            SELECT game_id,
                   ROUND(AVG(length * width * depth)) AS volume_avg
            FROM versions
            WHERE language = 'english'
            GROUP BY 1
        )
        SELECT vol.volume_avg
        FROM vol
        WHERE vol.game_id = games.id
    )
    """)

    # Create an index on avg_volume for better query performance.
    if not index_exists("games", op.f("ix_games_avg_box_volume")):
        op.create_index(
            op.f("ix_games_avg_box_volume"), "games", ["avg_box_volume"], unique=False
        )


def downgrade() -> None:
    # Remove the index first
    op.drop_index(op.f("ix_games_avg_box_volume"), table_name="games")

    # Then drop the column
    op.drop_column("games", "avg_box_volume")
