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


def table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in set(inspector.get_table_names())


def index_exists(table_name: str, index_name: str) -> bool:
    if not table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    """Upgrade schema."""
    if not table_exists("user_suggestions"):
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
    if not index_exists("user_suggestions", op.f("ix_user_suggestions_id")):
        op.create_index(
            op.f("ix_user_suggestions_id"), "user_suggestions", ["id"], unique=False
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop user_suggestions table
    op.drop_index(op.f("ix_user_suggestions_id"), table_name="user_suggestions")
    op.drop_table("user_suggestions")
