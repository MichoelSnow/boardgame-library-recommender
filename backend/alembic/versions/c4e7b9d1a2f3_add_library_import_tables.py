"""add library import tables

Revision ID: c4e7b9d1a2f3
Revises: b3f9a8d6c4e1
Create Date: 2026-03-16 12:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c4e7b9d1a2f3"
down_revision: Union[str, None] = "b3f9a8d6c4e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(
        index.get("name") == index_name for index in inspector.get_indexes(table_name)
    )


def _seed_initial_import_from_library_games(bind) -> None:
    seed_label = "legacy_library_games_seed"

    existing_import = bind.execute(
        sa.text(
            "SELECT id FROM library_imports WHERE label = :label",
        ),
        {"label": seed_label},
    ).fetchone()
    if existing_import:
        import_id = existing_import[0]
    else:
        bind.execute(
            sa.text(
                """
                INSERT INTO library_imports (
                    label,
                    import_method,
                    is_active,
                    created_at
                ) VALUES (
                    :label,
                    :import_method,
                    :is_active,
                    CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "label": seed_label,
                "import_method": "seed_existing",
                "is_active": True,
            },
        )
        import_id = bind.execute(
            sa.text("SELECT id FROM library_imports WHERE label = :label"),
            {"label": seed_label},
        ).fetchone()[0]

    bind.execute(
        sa.text("UPDATE library_imports SET is_active = false WHERE id != :import_id"),
        {"import_id": import_id},
    )
    bind.execute(
        sa.text("UPDATE library_imports SET is_active = true WHERE id = :import_id"),
        {"import_id": import_id},
    )

    bind.execute(
        sa.text(
            """
            INSERT INTO library_import_items (library_import_id, bgg_id)
            SELECT :import_id, DISTINCT_IDS.bgg_id
            FROM (
                SELECT DISTINCT bgg_id
                FROM library_games
                WHERE bgg_id IS NOT NULL
            ) AS DISTINCT_IDS
            WHERE NOT EXISTS (
                SELECT 1
                FROM library_import_items lii
                WHERE lii.library_import_id = :import_id
                  AND lii.bgg_id = DISTINCT_IDS.bgg_id
            )
            """
        ),
        {"import_id": import_id},
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "library_imports"):
        op.create_table(
            "library_imports",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("label", sa.String(), nullable=False),
            sa.Column("imported_by_user_id", sa.Integer(), nullable=True),
            sa.Column("activated_by_user_id", sa.Integer(), nullable=True),
            sa.Column("import_method", sa.String(), nullable=False),
            sa.Column(
                "is_active", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("activated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["activated_by_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["imported_by_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _table_exists(inspector, "library_import_items"):
        op.create_table(
            "library_import_items",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("library_import_id", sa.Integer(), nullable=False),
            sa.Column("bgg_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["library_import_id"], ["library_imports.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "library_import_id",
                "bgg_id",
                name="uq_library_import_items_import_bgg_id",
            ),
        )

    inspector = sa.inspect(bind)
    if not _index_exists(inspector, "library_imports", "ix_library_imports_id"):
        op.create_index(
            "ix_library_imports_id", "library_imports", ["id"], unique=False
        )
    if not _index_exists(inspector, "library_imports", "ix_library_imports_label"):
        op.create_index(
            "ix_library_imports_label",
            "library_imports",
            ["label"],
            unique=True,
        )
    if not _index_exists(inspector, "library_imports", "ix_library_imports_is_active"):
        op.create_index(
            "ix_library_imports_is_active",
            "library_imports",
            ["is_active"],
            unique=False,
        )
    if not _index_exists(
        inspector, "library_import_items", "ix_library_import_items_id"
    ):
        op.create_index(
            "ix_library_import_items_id",
            "library_import_items",
            ["id"],
            unique=False,
        )
    if not _index_exists(
        inspector, "library_import_items", "ix_library_import_items_library_import_id"
    ):
        op.create_index(
            "ix_library_import_items_library_import_id",
            "library_import_items",
            ["library_import_id"],
            unique=False,
        )
    if not _index_exists(
        inspector, "library_import_items", "ix_library_import_items_bgg_id"
    ):
        op.create_index(
            "ix_library_import_items_bgg_id",
            "library_import_items",
            ["bgg_id"],
            unique=False,
        )

    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS
                uq_library_imports_single_active
                ON library_imports (is_active)
                WHERE is_active = true
                """
            )
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "library_games"):
        _seed_initial_import_from_library_games(bind)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if bind.dialect.name == "postgresql":
        bind.execute(sa.text("DROP INDEX IF EXISTS uq_library_imports_single_active"))

    if _table_exists(inspector, "library_import_items"):
        if _index_exists(
            inspector, "library_import_items", "ix_library_import_items_bgg_id"
        ):
            op.drop_index(
                "ix_library_import_items_bgg_id", table_name="library_import_items"
            )
        if _index_exists(
            inspector,
            "library_import_items",
            "ix_library_import_items_library_import_id",
        ):
            op.drop_index(
                "ix_library_import_items_library_import_id",
                table_name="library_import_items",
            )
        if _index_exists(
            inspector, "library_import_items", "ix_library_import_items_id"
        ):
            op.drop_index(
                "ix_library_import_items_id", table_name="library_import_items"
            )
        op.drop_table("library_import_items")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "library_imports"):
        if _index_exists(inspector, "library_imports", "ix_library_imports_is_active"):
            op.drop_index("ix_library_imports_is_active", table_name="library_imports")
        if _index_exists(inspector, "library_imports", "ix_library_imports_label"):
            op.drop_index("ix_library_imports_label", table_name="library_imports")
        if _index_exists(inspector, "library_imports", "ix_library_imports_id"):
            op.drop_index("ix_library_imports_id", table_name="library_imports")
        op.drop_table("library_imports")
