"""add app settings table

Revision ID: b3f9a8d6c4e1
Revises: 1a2b3c4d5e6f
Create Date: 2026-03-15 20:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b3f9a8d6c4e1"
down_revision: Union[str, None] = "1a2b3c4d5e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(
        index.get("name") == index_name for index in inspector.get_indexes(table_name)
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "app_settings"):
        op.create_table(
            "app_settings",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("key", sa.String(), nullable=False),
            sa.Column("value", sa.String(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    if not _index_exists(inspector, "app_settings", "ix_app_settings_id"):
        op.create_index("ix_app_settings_id", "app_settings", ["id"], unique=False)
    if not _index_exists(inspector, "app_settings", "ix_app_settings_key"):
        op.create_index("ix_app_settings_key", "app_settings", ["key"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _table_exists(inspector, "app_settings"):
        if _index_exists(inspector, "app_settings", "ix_app_settings_key"):
            op.drop_index("ix_app_settings_key", table_name="app_settings")
        if _index_exists(inspector, "app_settings", "ix_app_settings_id"):
            op.drop_index("ix_app_settings_id", table_name="app_settings")
        op.drop_table("app_settings")
