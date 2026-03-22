"""drop legacy library_games table

Revision ID: f8a1d3c7b9e2
Revises: c4e7b9d1a2f3
Create Date: 2026-03-21 20:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f8a1d3c7b9e2"
down_revision: Union[str, None] = "c4e7b9d1a2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS library_games CASCADE")


def downgrade() -> None:
    op.create_table(
        "library_games",
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
    op.create_index("ix_library_games_bgg_id", "library_games", ["bgg_id"])
