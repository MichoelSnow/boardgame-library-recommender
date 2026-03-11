from sqlalchemy import UniqueConstraint
from sqlalchemy.sql.selectable import FromClause
from sqlalchemy.orm import Session
from types import SimpleNamespace
from typing import Any, cast

from backend.app import crud, models


class FakeQuery:
    def __init__(self, existing):
        self._existing = existing

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._existing


class FakeSession:
    def __init__(self, existing=None):
        self._existing = existing
        self.added = None
        self.commit_count = 0
        self.queried_model = None

    def query(self, model):
        self.queried_model = model
        return FakeQuery(self._existing)

    def add(self, relation):
        self.added = relation

    def commit(self):
        self.commit_count += 1


def test_add_mechanic_returns_existing_relation_without_duplicate_insert():
    existing_relation = SimpleNamespace(
        game_id=7,
        boardgamemechanic_name="Deck Building",
    )
    db = FakeSession(existing=existing_relation)

    result = crud.add_mechanic(
        cast(Session, db), game_id=7, mechanic_name="Deck Building"
    )

    assert result is existing_relation
    assert db.queried_model is models.Mechanic
    assert db.added is None
    assert db.commit_count == 0


def test_add_mechanic_creates_relation_when_missing():
    db = FakeSession()

    result = crud.add_mechanic(
        cast(Session, db), game_id=9, mechanic_name="Worker Placement"
    )
    result_any = cast(Any, result)

    assert isinstance(result, models.Mechanic)
    assert result_any.game_id == 9
    assert result_any.boardgamemechanic_name == "Worker Placement"
    assert db.queried_model is models.Mechanic
    assert db.added is result
    assert db.commit_count == 1


def test_relation_tables_define_name_uniqueness_constraints():
    expected_constraints: dict[FromClause, tuple[str, str]] = {
        models.Mechanic.__table__: ("game_id", "boardgamemechanic_name"),
        models.Category.__table__: ("game_id", "boardgamecategory_name"),
        models.Designer.__table__: ("game_id", "boardgamedesigner_name"),
        models.Artist.__table__: ("game_id", "boardgameartist_name"),
        models.Publisher.__table__: ("game_id", "boardgamepublisher_name"),
    }

    for table, expected_columns in expected_constraints.items():
        table_with_constraints = cast(Any, table)
        unique_constraints = [
            constraint
            for constraint in table_with_constraints.constraints
            if isinstance(constraint, UniqueConstraint)
        ]
        assert any(
            tuple(column.name for column in constraint.columns) == expected_columns
            for constraint in unique_constraints
        )
