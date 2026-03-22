from types import SimpleNamespace

import pandas as pd

import backend.app.import_data as import_data


class _FakeSession:
    def __init__(self):
        self.committed = False
        self.rolled_back = False
        self.closed = False
        self.executed_queries = []

    def execute(self, query):
        self.executed_queries.append(str(query))
        return SimpleNamespace(rowcount=0)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_clear_import_tables_for_reimport_postgres_uses_truncate(monkeypatch):
    fake_session = _FakeSession()
    monkeypatch.setattr(import_data, "SessionLocal", lambda: fake_session)
    monkeypatch.setattr(
        import_data,
        "engine",
        SimpleNamespace(dialect=SimpleNamespace(name="postgresql")),
    )

    import_data.clear_import_tables_for_reimport()

    assert fake_session.committed is True
    assert fake_session.closed is True
    assert fake_session.rolled_back is False
    assert len(fake_session.executed_queries) == 1
    assert fake_session.executed_queries[0].startswith("TRUNCATE TABLE ")
    assert " RESTART IDENTITY CASCADE" in fake_session.executed_queries[0]
    assert "library_games" not in fake_session.executed_queries[0]


def test_clear_import_tables_for_reimport_non_postgres_uses_delete(monkeypatch):
    fake_session = _FakeSession()
    monkeypatch.setattr(import_data, "SessionLocal", lambda: fake_session)
    monkeypatch.setattr(
        import_data,
        "engine",
        SimpleNamespace(dialect=SimpleNamespace(name="sqlite")),
    )

    import_data.clear_import_tables_for_reimport()

    assert fake_session.committed is True
    assert fake_session.closed is True
    assert fake_session.rolled_back is False
    assert len(fake_session.executed_queries) == len(import_data.IMPORT_TABLES)
    assert all(
        query.startswith("DELETE FROM ") for query in fake_session.executed_queries
    )


def test_create_related_objects_dedupes_duplicate_designer_names():
    related_data = {
        "boardgamedesigner": pd.DataFrame(
            [
                {
                    "game_id": 2853,
                    "boardgamedesigner_id": 1156,
                    "boardgamedesigner_name": "Fritz Bronner",
                },
                {
                    "game_id": 2853,
                    "boardgamedesigner_id": 155388,
                    "boardgamedesigner_name": "Fritz Bronner",
                },
                {
                    "game_id": 2853,
                    "boardgamedesigner_id": 760,
                    "boardgamedesigner_name": "John Olsen",
                },
            ]
        )
    }

    related_objects = import_data.create_related_objects(
        game_id=2853,
        game_data=pd.Series({"id": 2853}),
        related_data=related_data,
    )

    designers = [obj for obj in related_objects if obj.__class__.__name__ == "Designer"]
    names = [designer.boardgamedesigner_name for designer in designers]
    assert names == ["Fritz Bronner", "John Olsen"]


def test_dedupe_games_dataframe_removes_duplicate_ids():
    games_df = pd.DataFrame(
        [
            {"id": 1, "name": "A"},
            {"id": 2, "name": "B"},
            {"id": 1, "name": "A (duplicate)"},
        ]
    )

    deduped_df, duplicate_count = import_data.dedupe_games_dataframe(games_df)

    assert duplicate_count == 1
    assert deduped_df["id"].tolist() == [1, 2]


class _FakeLockResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _FakeLockConnection:
    def __init__(self, acquired=True):
        self._acquired = acquired
        self.closed = False
        self.commit_calls = 0
        self.execute_calls = []

    def execute(self, statement, params):
        self.execute_calls.append((str(statement), params))
        if "pg_try_advisory_lock" in str(statement):
            return _FakeLockResult(self._acquired)
        return _FakeLockResult(True)

    def close(self):
        self.closed = True

    def commit(self):
        self.commit_calls += 1


def test_acquire_import_data_lock_postgres_acquired(monkeypatch):
    fake_connection = _FakeLockConnection(acquired=True)
    monkeypatch.setattr(
        import_data,
        "engine",
        SimpleNamespace(
            dialect=SimpleNamespace(name="postgresql"),
            connect=lambda: fake_connection,
        ),
    )

    lock_connection = import_data.acquire_import_data_lock()

    assert lock_connection is fake_connection
    assert fake_connection.closed is False
    assert fake_connection.commit_calls == 1
    assert any(
        "pg_try_advisory_lock" in statement
        for statement, _ in fake_connection.execute_calls
    )


def test_acquire_import_data_lock_postgres_rejected(monkeypatch):
    fake_connection = _FakeLockConnection(acquired=False)
    monkeypatch.setattr(
        import_data,
        "engine",
        SimpleNamespace(
            dialect=SimpleNamespace(name="postgresql"),
            connect=lambda: fake_connection,
        ),
    )

    try:
        import_data.acquire_import_data_lock()
        assert False, "Expected RuntimeError when advisory lock is already held"
    except RuntimeError as exc:
        assert "already active" in str(exc)
    assert fake_connection.closed is True
    assert fake_connection.commit_calls == 0


def test_release_import_data_lock_unlocks_and_commits():
    fake_connection = _FakeLockConnection(acquired=True)

    import_data.release_import_data_lock(fake_connection)

    assert fake_connection.closed is True
    assert fake_connection.commit_calls == 1
    assert any(
        "pg_advisory_unlock" in statement
        for statement, _ in fake_connection.execute_calls
    )
