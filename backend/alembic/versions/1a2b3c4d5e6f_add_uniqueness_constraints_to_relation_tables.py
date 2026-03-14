"""add_uniqueness_constraints_to_relation_tables

Revision ID: 1a2b3c4d5e6f
Revises: 4f77595d6dba
Create Date: 2026-02-28 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1a2b3c4d5e6f"
down_revision: Union[str, None] = "4f77595d6dba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def deduplicate_relation_table(table_name: str, name_column: str) -> None:
    op.execute(
        f"""
        DELETE FROM {table_name}
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM {table_name}
            GROUP BY game_id, {name_column}
        )
        """
    )


def unique_constraint_exists(table_name: str, constraint_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return constraint_name in {
        constraint["name"]
        for constraint in inspector.get_unique_constraints(table_name)
    }


def create_unique_constraint_if_missing(
    table_name: str, constraint_name: str, columns: list[str]
) -> None:
    if unique_constraint_exists(table_name, constraint_name):
        return
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.create_unique_constraint(constraint_name, columns)


def upgrade() -> None:
    deduplicate_relation_table("mechanics", "boardgamemechanic_name")
    deduplicate_relation_table("categories", "boardgamecategory_name")
    deduplicate_relation_table("designers", "boardgamedesigner_name")
    deduplicate_relation_table("artists", "boardgameartist_name")
    deduplicate_relation_table("publishers", "boardgamepublisher_name")

    create_unique_constraint_if_missing(
        "mechanics",
        "uq_mechanics_game_id_name",
        ["game_id", "boardgamemechanic_name"],
    )
    create_unique_constraint_if_missing(
        "categories",
        "uq_categories_game_id_name",
        ["game_id", "boardgamecategory_name"],
    )
    create_unique_constraint_if_missing(
        "designers",
        "uq_designers_game_id_name",
        ["game_id", "boardgamedesigner_name"],
    )
    create_unique_constraint_if_missing(
        "artists",
        "uq_artists_game_id_name",
        ["game_id", "boardgameartist_name"],
    )
    create_unique_constraint_if_missing(
        "publishers",
        "uq_publishers_game_id_name",
        ["game_id", "boardgamepublisher_name"],
    )


def downgrade() -> None:
    with op.batch_alter_table("publishers") as batch_op:
        batch_op.drop_constraint("uq_publishers_game_id_name", type_="unique")

    with op.batch_alter_table("artists") as batch_op:
        batch_op.drop_constraint("uq_artists_game_id_name", type_="unique")

    with op.batch_alter_table("designers") as batch_op:
        batch_op.drop_constraint("uq_designers_game_id_name", type_="unique")

    with op.batch_alter_table("categories") as batch_op:
        batch_op.drop_constraint("uq_categories_game_id_name", type_="unique")

    with op.batch_alter_table("mechanics") as batch_op:
        batch_op.drop_constraint("uq_mechanics_game_id_name", type_="unique")
