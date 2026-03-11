"""Add user_suggestions table

Revision ID: 594a7422f114
Revises: 6d4ea4dc16c2
Create Date: 2025-07-12 21:16:40.475282

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "594a7422f114"
down_revision: Union[str, None] = "6d4ea4dc16c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create user_suggestions table
    op.create_table(
        "user_suggestions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("comment", sa.String(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_user_suggestions_id"), "user_suggestions", ["id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop user_suggestions table
    op.drop_index(op.f("ix_user_suggestions_id"), table_name="user_suggestions")
    op.drop_table("user_suggestions")
