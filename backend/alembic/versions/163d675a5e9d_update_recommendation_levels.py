"""update_recommendation_levels

Revision ID: 163d675a5e9d
Revises: d258c28b421e
Create Date: 2025-06-08 21:27:09.508688

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "163d675a5e9d"
down_revision: Union[str, None] = "d258c28b421e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update recommendation_level based on the highest value among best, recommended, and not_recommended
    op.execute("""
        UPDATE suggested_players 
        SET recommendation_level = CASE
            WHEN best >= recommended AND best >= not_recommended THEN 'best'
            WHEN recommended >= best AND recommended >= not_recommended THEN 'recommended'
            ELSE 'not_recommended'
        END
    """)


def downgrade() -> None:
    # No downgrade needed as we're just updating values
    pass
