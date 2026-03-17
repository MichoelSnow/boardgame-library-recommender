from sqlalchemy import UniqueConstraint
from types import SimpleNamespace

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


class FakeLibraryImportSession:
    def __init__(self, existing=None):
        self._existing = existing
        self.added = None
        self.flushed = False
        self.execute_calls = []
        self.commit_count = 0
        self.refreshed = None

    def query(self, model):
        return FakeQuery(self._existing)

    def add(self, obj):
        self.added = obj

    def flush(self):
        self.flushed = True
        if self.added is not None and getattr(self.added, "id", None) is None:
            self.added.id = 42

    def execute(self, statement, params):
        self.execute_calls.append((statement, params))

    def commit(self):
        self.commit_count += 1

    def refresh(self, obj):
        self.refreshed = obj


def test_add_mechanic_returns_existing_relation_without_duplicate_insert():
    existing_relation = SimpleNamespace(
        game_id=7,
        boardgamemechanic_name="Deck Building",
    )
    db = FakeSession(existing=existing_relation)

    result = crud.add_mechanic(db, game_id=7, mechanic_name="Deck Building")

    assert result is existing_relation
    assert db.queried_model is models.Mechanic
    assert db.added is None
    assert db.commit_count == 0


def test_add_mechanic_creates_relation_when_missing():
    db = FakeSession()

    result = crud.add_mechanic(db, game_id=9, mechanic_name="Worker Placement")

    assert isinstance(result, models.Mechanic)
    assert result.game_id == 9
    assert result.boardgamemechanic_name == "Worker Placement"
    assert db.queried_model is models.Mechanic
    assert db.added is result
    assert db.commit_count == 1


def test_relation_tables_define_name_uniqueness_constraints():
    expected_constraints = {
        models.Mechanic.__table__: ("game_id", "boardgamemechanic_name"),
        models.Category.__table__: ("game_id", "boardgamecategory_name"),
        models.Designer.__table__: ("game_id", "boardgamedesigner_name"),
        models.Artist.__table__: ("game_id", "boardgameartist_name"),
        models.Publisher.__table__: ("game_id", "boardgamepublisher_name"),
    }

    for table, expected_columns in expected_constraints.items():
        unique_constraints = [
            constraint
            for constraint in table.constraints
            if isinstance(constraint, UniqueConstraint)
        ]
        assert any(
            tuple(column.name for column in constraint.columns) == expected_columns
            for constraint in unique_constraints
        )


def test_create_library_import_uses_chunked_core_insert(monkeypatch):
    db = FakeLibraryImportSession(existing=None)
    monkeypatch.setattr(crud, "LIBRARY_IMPORT_INSERT_BATCH_SIZE", 2)

    library_import = crud.create_library_import(
        db,
        label="Spring Batch",
        import_method="csv_upload",
        imported_by_user_id=7,
        bgg_ids=[10, 20, 30, 40, 50],
        activate=False,
    )

    assert library_import.id == 42
    assert db.flushed is True
    assert db.commit_count == 1
    assert db.refreshed is library_import
    assert len(db.execute_calls) == 3
    assert [len(params) for _, params in db.execute_calls] == [2, 2, 1]
    inserted_ids = [row["bgg_id"] for _, params in db.execute_calls for row in params]
    assert inserted_ids == [10, 20, 30, 40, 50]
    assert all(
        row["library_import_id"] == 42
        for _, params in db.execute_calls
        for row in params
    )
