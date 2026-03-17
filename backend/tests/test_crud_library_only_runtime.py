from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import crud, models


def _seed_board_games(db):
    db.add_all(
        [
            models.BoardGame(id=1, name="Game 1", rank=1),
            models.BoardGame(id=2, name="Game 2", rank=2),
            models.BoardGame(id=3, name="Game 3", rank=3),
        ]
    )
    db.flush()


def test_get_games_library_only_prefers_active_import() -> None:
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    _seed_board_games(db)
    db.add(models.LibraryGame(name="Legacy", bgg_id=2))
    db.flush()
    active_import = models.LibraryImport(
        label="active_import",
        import_method="csv_upload",
        is_active=True,
    )
    db.add(active_import)
    db.flush()
    db.add(models.LibraryImportItem(library_import_id=active_import.id, bgg_id=3))
    db.commit()

    games, total = crud.get_games(
        db, skip=0, limit=10, sort_by="rank", library_only=True
    )

    assert total == 1
    assert [game.id for game in games] == [3]


def test_get_games_library_only_falls_back_to_legacy_table() -> None:
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    _seed_board_games(db)
    db.add(models.LibraryGame(name="Legacy", bgg_id=2))
    db.commit()

    games, total = crud.get_games(
        db, skip=0, limit=10, sort_by="rank", library_only=True
    )

    assert total == 1
    assert [game.id for game in games] == [2]


def test_get_games_library_only_total_updates_when_active_import_changes() -> None:
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    _seed_board_games(db)

    import_one = models.LibraryImport(
        label="import_one",
        import_method="csv_upload",
        is_active=True,
    )
    db.add(import_one)
    db.flush()
    db.add(models.LibraryImportItem(library_import_id=import_one.id, bgg_id=2))
    db.commit()

    _, total_one = crud.get_games(
        db, skip=0, limit=10, sort_by="rank", library_only=True
    )
    assert total_one == 1

    import_one.is_active = False
    import_two = models.LibraryImport(
        label="import_two",
        import_method="csv_upload",
        is_active=True,
    )
    db.add(import_two)
    db.flush()
    db.add_all(
        [
            models.LibraryImportItem(library_import_id=import_two.id, bgg_id=2),
            models.LibraryImportItem(library_import_id=import_two.id, bgg_id=3),
        ]
    )
    db.commit()

    _, total_two = crud.get_games(
        db, skip=0, limit=10, sort_by="rank", library_only=True
    )
    assert total_two == 2
