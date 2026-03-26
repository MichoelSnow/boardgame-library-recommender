import threading
import time
from datetime import datetime
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import exists, func, insert, select
from sqlalchemy.sql import or_, and_
from . import models, schemas, security
from typing import Any, List, Optional
import logging
import secrets

logger = logging.getLogger(__name__)

_TOTAL_CACHE_LOCK = threading.Lock()
_TOTAL_CACHE_TTL_SECONDS = 120
_TOTAL_CACHE_MAX_ENTRIES = 128
_total_count_cache: dict[tuple[Any, ...], tuple[float, int]] = {}
LIBRARY_IMPORT_INSERT_BATCH_SIZE = 1000


def _cache_get_total(cache_key: tuple[Any, ...]) -> Optional[int]:
    now = time.time()
    with _TOTAL_CACHE_LOCK:
        entry = _total_count_cache.get(cache_key)
        if entry is None:
            return None
        expiry, value = entry
        if expiry < now:
            _total_count_cache.pop(cache_key, None)
            return None
        return value


def _cache_set_total(cache_key: tuple[Any, ...], value: int) -> None:
    now = time.time()
    with _TOTAL_CACHE_LOCK:
        if len(_total_count_cache) >= _TOTAL_CACHE_MAX_ENTRIES:
            # Remove one oldest-expiry entry to cap memory growth.
            oldest_key = min(_total_count_cache.items(), key=lambda item: item[1][0])[0]
            _total_count_cache.pop(oldest_key, None)
        _total_count_cache[cache_key] = (now + _TOTAL_CACHE_TTL_SECONDS, value)


def clear_total_count_cache() -> None:
    """Clear cached game totals so pagination reflects fresh library state."""
    with _TOTAL_CACHE_LOCK:
        _total_count_cache.clear()


def _build_total_cache_key(
    *,
    search: Optional[str],
    players: Optional[int],
    designer_id: Optional[str],
    artist_id: Optional[str],
    recommendations: Optional[str],
    weight: Optional[str],
    mechanics: Optional[str],
    categories: Optional[str],
    library_only: Optional[bool],
    runtime_library_version: Optional[str] = None,
) -> tuple[Any, ...]:
    return (
        search,
        players,
        designer_id,
        artist_id,
        recommendations,
        weight,
        mechanics,
        categories,
        bool(library_only),
        runtime_library_version,
    )


def _approximate_total_from_page(skip: int, limit: int, page_size: int) -> int:
    # Lower-bound + small lookahead estimate without running a full COUNT(*).
    if page_size < limit:
        return skip + page_size
    return skip + page_size + limit


def _get_or_create_named_relation(
    db: Session,
    model,
    game_id: int,
    name_field: str,
    name_value: str,
):
    """Return an existing named relation row or create it if missing."""
    existing = (
        db.query(model)
        .filter(
            model.game_id == game_id,
            getattr(model, name_field) == name_value,
        )
        .first()
    )
    if existing is not None:
        return existing

    relation = model(
        game_id=game_id,
        **{name_field: name_value},
    )
    db.add(relation)
    db.commit()
    return relation


# def get_games(db: Session, skip: int = 0, limit: int = 100):
#     return db.query(models.BoardGame).offset(skip).limit(limit).all()


def get_games(
    db: Session,
    skip: int = 0,
    limit: int = 24,
    sort_by: Optional[str] = "rank",
    search: Optional[str] = None,
    players: Optional[int] = None,
    designer_id: Optional[str] = None,
    artist_id: Optional[str] = None,
    recommendations: Optional[str] = None,
    weight: Optional[str] = None,
    mechanics: Optional[str] = None,
    categories: Optional[str] = None,
    library_only: Optional[bool] = False,
):
    try:
        # Start with a base query - only load main game fields initially
        query = db.query(models.BoardGame)

        if sort_by == "recommendation_score":
            sort_by = "rank"

        active_import = None
        runtime_library_version = None
        if library_only:
            active_import = get_active_library_import(db)
            runtime_library_version = (
                f"import:{active_import.id}" if active_import is not None else "legacy"
            )
            query = query.filter(
                build_runtime_library_only_filter(db, active_import=active_import)
            )

        # Apply simple filters first
        if search:
            search_term = f"%{search}%"
            query = query.filter(models.BoardGame.name.ilike(search_term))

        if weight:
            weight_list = weight.split(",")
            weight_conditions = []
            if "beginner" in weight_list:
                weight_conditions.append(models.BoardGame.average_weight <= 2.0)
            if "midweight" in weight_list:
                weight_conditions.append(
                    and_(
                        models.BoardGame.average_weight > 2.0,
                        models.BoardGame.average_weight < 4.0,
                    )
                )
            if "heavy" in weight_list:
                weight_conditions.append(models.BoardGame.average_weight >= 4.0)

            if weight_conditions:
                query = query.filter(or_(*weight_conditions))

        # Apply relationship filters using efficient subqueries with timeout protection
        if designer_id:
            try:
                designer_ids = [int(d_id) for d_id in designer_id.split(",")]
                subquery = (
                    select(models.BoardGame.id)
                    .join(models.BoardGame.designers)
                    .filter(models.Designer.boardgamedesigner_id.in_(designer_ids))
                    .group_by(models.BoardGame.id)
                    .having(
                        func.count(models.Designer.boardgamedesigner_id)
                        == len(designer_ids)
                    )
                    .subquery()
                )
                query = query.filter(models.BoardGame.id.in_(subquery))
            except Exception as e:
                logger.warning(f"Error applying designer filter: {str(e)}")
                # Continue without designer filter if it fails

        if artist_id:
            try:
                artist_ids = [int(a_id) for a_id in artist_id.split(",")]
                subquery = (
                    select(models.BoardGame.id)
                    .join(models.BoardGame.artists)
                    .filter(models.Artist.boardgameartist_id.in_(artist_ids))
                    .group_by(models.BoardGame.id)
                    .having(
                        func.count(models.Artist.boardgameartist_id) == len(artist_ids)
                    )
                    .subquery()
                )
                query = query.filter(models.BoardGame.id.in_(subquery))
            except Exception as e:
                logger.warning(f"Error applying artist filter: {str(e)}")
                # Continue without artist filter if it fails

        if mechanics:
            try:
                mechanic_ids = [int(m_id) for m_id in mechanics.split(",")]
                subquery = (
                    select(models.BoardGame.id)
                    .join(models.BoardGame.mechanics)
                    .filter(models.Mechanic.boardgamemechanic_id.in_(mechanic_ids))
                    .group_by(models.BoardGame.id)
                    .having(
                        func.count(models.Mechanic.boardgamemechanic_id)
                        == len(mechanic_ids)
                    )
                    .subquery()
                )
                query = query.filter(models.BoardGame.id.in_(subquery))
            except Exception as e:
                logger.warning(f"Error applying mechanics filter: {str(e)}")
                # Continue without mechanics filter if it fails

        if categories:
            try:
                category_ids = [int(c_id) for c_id in categories.split(",")]
                subquery = (
                    select(models.BoardGame.id)
                    .join(models.BoardGame.categories)
                    .filter(models.Category.boardgamecategory_id.in_(category_ids))
                    .group_by(models.BoardGame.id)
                    .having(
                        func.count(models.Category.boardgamecategory_id)
                        == len(category_ids)
                    )
                    .subquery()
                )
                query = query.filter(models.BoardGame.id.in_(subquery))
            except Exception as e:
                logger.warning(f"Error applying categories filter: {str(e)}")
                # Continue without categories filter if it fails

        if recommendations:
            try:
                rec_list = recommendations.split(",")
                # Need to join with suggested_players table for recommendations filter
                query = query.join(models.BoardGame.suggested_players)
                if players:
                    query = query.filter(models.SuggestedPlayer.player_count == players)
                if "best" in rec_list:
                    query = query.filter(
                        models.SuggestedPlayer.recommendation_level == "best"
                    )
                if "recommended" in rec_list:
                    query = query.filter(
                        models.SuggestedPlayer.recommendation_level == "recommended"
                    )
            except Exception as e:
                logger.warning(f"Error applying recommendations filter: {str(e)}")
                # Continue without recommendations filter if it fails
        elif players:
            try:
                # Use min_players and max_players from games table instead of suggested_players
                query = query.filter(
                    and_(
                        models.BoardGame.min_players <= players,
                        models.BoardGame.max_players >= players,
                    )
                )
            except Exception as e:
                logger.warning(f"Error applying players filter: {str(e)}")
                # Continue without players filter if it fails

        # Verify that the sort_by field exists in the model, or handle special cases
        if sort_by.startswith("name_"):
            order_field = "name"
            order_dir = sort_by.split("_")[1]
        elif hasattr(models.BoardGame, sort_by):
            order_field = sort_by
            order_dir = "asc"
        else:
            raise ValueError(f"Invalid sort field: {sort_by}")

        # Order by the selected field, with NULLs last
        rank_field = getattr(models.BoardGame, order_field)
        if order_dir == "desc":
            query = query.order_by(rank_field.desc().nullslast())
        else:
            query = query.order_by(rank_field.asc().nullslast())

        # Avoid cartesian row explosion from multi-collection joinedload by using
        # selectinload for list relationships.
        query = query.options(
            selectinload(models.BoardGame.mechanics),
            selectinload(models.BoardGame.categories),
            selectinload(models.BoardGame.suggested_players),
        )

        # Apply pagination with timeout protection
        try:
            games = query.offset(skip).limit(limit).all()
        except Exception as e:
            logger.error(f"Error fetching games: {str(e)}")
            games = []

        cache_key = _build_total_cache_key(
            search=search,
            players=players,
            designer_id=designer_id,
            artist_id=artist_id,
            recommendations=recommendations,
            weight=weight,
            mechanics=mechanics,
            categories=categories,
            library_only=library_only,
            runtime_library_version=runtime_library_version,
        )

        cached_total = _cache_get_total(cache_key)
        if cached_total is not None:
            total = cached_total
        else:
            try:
                total = query.order_by(None).count()
                _cache_set_total(cache_key, total)
            except Exception as e:
                logger.error(f"Error getting total count: {str(e)}")
                total = _approximate_total_from_page(skip, limit, len(games))
                _cache_set_total(cache_key, total)

        # Keep total non-decreasing within a cache window so pagination controls
        # do not jump backward while users browse pages.
        observed_floor = skip + len(games)
        if observed_floor > total:
            total = observed_floor
            _cache_set_total(cache_key, total)

        return games, total
    except Exception as e:
        logger.error(f"Error in get_games: {str(e)}")
        raise


def get_game(db: Session, game_id: int):
    return db.query(models.BoardGame).filter(models.BoardGame.id == game_id).first()


def create_game(db: Session, game: schemas.BoardGameCreate):
    db_game = models.BoardGame(
        **game.dict(
            exclude={"mechanics", "categories", "designers", "artists", "publishers"}
        )
    )
    db.add(db_game)
    db.commit()
    db.refresh(db_game)
    return db_game


def get_filter_options(db: Session):
    designers = db.query(models.Designer.boardgamedesigner_name).distinct().all()
    mechanics = db.query(models.Mechanic.boardgamemechanic_name).distinct().all()
    categories = db.query(models.Category.boardgamecategory_name).distinct().all()
    publishers = db.query(models.Publisher.boardgamepublisher_name).distinct().all()

    return {
        "designers": [d[0] for d in designers],
        "mechanics": [m[0] for m in mechanics],
        "categories": [c[0] for c in categories],
        "publishers": [p[0] for p in publishers],
    }


def get_mechanics_cached(db: Session, skip: int = 0, limit: int = 100):
    """Get mechanics with pagination and caching-friendly structure."""
    mechanics = (
        db.query(
            models.Mechanic.boardgamemechanic_id, models.Mechanic.boardgamemechanic_name
        )
        .distinct()
        .order_by(models.Mechanic.boardgamemechanic_name)
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [
        {"boardgamemechanic_id": m[0], "boardgamemechanic_name": m[1]}
        for m in mechanics
    ]


def get_categories_cached(db: Session, skip: int = 0, limit: int = 100):
    """Get categories with pagination and caching-friendly structure."""
    categories = (
        db.query(
            models.Category.boardgamecategory_id, models.Category.boardgamecategory_name
        )
        .distinct()
        .order_by(models.Category.boardgamecategory_name)
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [
        {"boardgamecategory_id": c[0], "boardgamecategory_name": c[1]}
        for c in categories
    ]


def get_mechanics_count(db: Session):
    """Get total count of unique mechanics for pagination."""
    return db.query(models.Mechanic.boardgamemechanic_id).distinct().count()


def add_mechanic(db: Session, game_id: int, mechanic_name: str):
    return _get_or_create_named_relation(
        db=db,
        model=models.Mechanic,
        game_id=game_id,
        name_field="boardgamemechanic_name",
        name_value=mechanic_name,
    )


def add_category(db: Session, game_id: int, category_name: str):
    return _get_or_create_named_relation(
        db=db,
        model=models.Category,
        game_id=game_id,
        name_field="boardgamecategory_name",
        name_value=category_name,
    )


def add_designer(db: Session, game_id: int, designer_name: str):
    return _get_or_create_named_relation(
        db=db,
        model=models.Designer,
        game_id=game_id,
        name_field="boardgamedesigner_name",
        name_value=designer_name,
    )


def add_artist(db: Session, game_id: int, artist_name: str):
    return _get_or_create_named_relation(
        db=db,
        model=models.Artist,
        game_id=game_id,
        name_field="boardgameartist_name",
        name_value=artist_name,
    )


def add_publisher(db: Session, game_id: int, publisher_name: str):
    return _get_or_create_named_relation(
        db=db,
        model=models.Publisher,
        game_id=game_id,
        name_field="boardgamepublisher_name",
        name_value=publisher_name,
    )


def get_mechanics_by_frequency(db: Session):
    """Returns mechanics sorted by frequency of use in games."""
    return (
        db.query(
            models.Mechanic.boardgamemechanic_id,
            models.Mechanic.boardgamemechanic_name,
            func.count(models.Mechanic.game_id).label("frequency"),
        )
        .group_by(
            models.Mechanic.boardgamemechanic_id, models.Mechanic.boardgamemechanic_name
        )
        .order_by(func.count(models.Mechanic.game_id).desc())
        .all()
    )


def get_categories_by_frequency(db: Session):
    return (
        db.query(
            models.Category.boardgamecategory_id,
            models.Category.boardgamecategory_name,
            func.count(models.Category.boardgamecategory_id).label("frequency"),
        )
        .group_by(
            models.Category.boardgamecategory_id, models.Category.boardgamecategory_name
        )
        .order_by(func.count(models.Category.boardgamecategory_id).desc())
        .all()
    )


def get_recommendations(
    db: Session,
    limit: int = 20,
    liked_games: Optional[List[int]] = None,
    disliked_games: Optional[List[int]] = None,
    anti_weight: float = 1.0,
    library_only: Optional[bool] = False,
    recommender_mode: str = "hybrid",
    collaborative_weight: float | None = None,
    content_weight: float | None = None,
    quality_weight: float | None = None,
) -> List[models.BoardGame]:
    """
    Get game recommendations based on liked and disliked games.
    """
    from . import recommender  # Lazy import to avoid circular dependencies

    return recommender.get_recommendations(
        db=db,
        limit=limit,
        liked_games=liked_games,
        disliked_games=disliked_games,
        anti_weight=anti_weight,
        library_only=library_only,
        recommender_mode=recommender_mode,
        collaborative_weight=collaborative_weight,
        content_weight=content_weight,
        quality_weight=quality_weight,
    )


def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_by_username(db: Session, username: str):
    return (
        db.query(models.User)
        .filter(func.lower(models.User.username) == username.lower())
        .first()
    )


def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = security.get_password_hash(user.password)
    db_user = models.User(
        username=user.username.lower(),
        hashed_password=hashed_password,
        is_admin=user.is_admin if hasattr(user, "is_admin") else False,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def authenticate_user(db: Session, username: str, password: str):
    user = get_user_by_username(db, username.lower())
    if not user:
        return False
    if not security.verify_password(password, user.hashed_password):
        return False
    return user


def create_user_suggestion(
    db: Session, user_id: int, suggestion: schemas.UserSuggestionCreate
):
    db_suggestion = models.UserSuggestion(user_id=user_id, comment=suggestion.comment)
    db.add(db_suggestion)
    db.commit()
    db.refresh(db_suggestion)
    return db_suggestion


def get_or_create_guest_user(
    db: Session, username: str = security.CONVENTION_GUEST_USERNAME
):
    guest_user = get_user_by_username(db, username)
    if guest_user:
        return guest_user

    guest_user = models.User(
        username=username.lower(),
        hashed_password=security.get_password_hash(secrets.token_urlsafe(48)),
        is_admin=False,
        is_active=True,
    )
    db.add(guest_user)
    db.commit()
    db.refresh(guest_user)
    return guest_user


def change_user_password(
    db: Session, user_id: int, old_password: str, new_password: str
):
    user = get_user(db, user_id)
    if not user:
        return False
    if not security.verify_password(old_password, user.hashed_password):
        return False

    user.hashed_password = security.get_password_hash(new_password)
    db.commit()
    return True


def admin_reset_password(db: Session, username: str, new_password: str):
    user = get_user_by_username(db, username.lower())
    if not user:
        return False

    user.hashed_password = security.get_password_hash(new_password)
    db.commit()
    return True


def get_users(db: Session):
    return db.query(models.User).order_by(models.User.username.asc()).all()


def update_user_admin_flags(
    db: Session,
    user_id: int,
    *,
    is_admin: bool | None = None,
    is_active: bool | None = None,
):
    user = get_user(db, user_id)
    if not user:
        return None
    if is_admin is not None:
        user.is_admin = is_admin
    if is_active is not None:
        user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user


def admin_reset_password_by_user_id(db: Session, user_id: int, new_password: str):
    user = get_user(db, user_id)
    if not user:
        return False
    user.hashed_password = security.get_password_hash(new_password)
    db.commit()
    return True


def get_app_setting(db: Session, key: str):
    return db.query(models.AppSetting).filter(models.AppSetting.key == key).first()


def upsert_app_setting(db: Session, key: str, value: str):
    setting = get_app_setting(db, key)
    if setting:
        setting.value = value
    else:
        setting = models.AppSetting(key=key, value=value)
        db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting


def delete_app_setting(db: Session, key: str) -> bool:
    setting = get_app_setting(db, key)
    if not setting:
        return False
    db.delete(setting)
    db.commit()
    return True


def get_active_library_import(db: Session) -> Optional[models.LibraryImport]:
    return (
        db.query(models.LibraryImport)
        .filter(models.LibraryImport.is_active.is_(True))
        .order_by(models.LibraryImport.id.desc())
        .first()
    )


def build_runtime_library_only_filter(
    db: Session,
    *,
    active_import: Optional[models.LibraryImport] = None,
):
    """
    Build a library-only filter expression for BoardGame queries.

    Uses only the active library import items table.
    """
    if active_import is None:
        active_import = get_active_library_import(db)
    if active_import is None:
        return models.BoardGame.id == -1
    return exists().where(
        and_(
            models.LibraryImportItem.library_import_id == active_import.id,
            models.LibraryImportItem.bgg_id == models.BoardGame.id,
        )
    )


def get_library_ids_for_runtime(db: Session) -> list[int]:
    """Return active library IDs from imports only."""
    active_import = get_active_library_import(db)
    if active_import is None:
        return []
    rows = (
        db.query(models.LibraryImportItem.bgg_id)
        .filter(models.LibraryImportItem.library_import_id == active_import.id)
        .all()
    )
    return [row[0] for row in rows if row[0] is not None]


def get_games_count(db: Session) -> int:
    """Return total count of catalog games."""
    return db.query(models.BoardGame.id).count()


def list_library_import_summaries(db: Session) -> list[dict[str, Any]]:
    imports = (
        db.query(models.LibraryImport).order_by(models.LibraryImport.id.desc()).all()
    )
    if not imports:
        return []

    import_ids = [item.id for item in imports]
    counts = {
        row.library_import_id: row.count
        for row in (
            db.query(
                models.LibraryImportItem.library_import_id,
                func.count(models.LibraryImportItem.id).label("count"),
            )
            .filter(models.LibraryImportItem.library_import_id.in_(import_ids))
            .group_by(models.LibraryImportItem.library_import_id)
            .all()
        )
    }

    user_ids = {
        user_id
        for item in imports
        for user_id in (item.imported_by_user_id, item.activated_by_user_id)
        if user_id is not None
    }
    users_by_id: dict[int, str] = {}
    if user_ids:
        users_by_id = {
            user.id: user.username
            for user in db.query(models.User)
            .filter(models.User.id.in_(list(user_ids)))
            .all()
        }

    rows: list[dict[str, Any]] = []
    for item in imports:
        rows.append(
            {
                "id": item.id,
                "label": item.label,
                "import_method": item.import_method,
                "is_active": item.is_active,
                "created_at": item.created_at,
                "activated_at": item.activated_at,
                "imported_by_user_id": item.imported_by_user_id,
                "activated_by_user_id": item.activated_by_user_id,
                "imported_by_username": users_by_id.get(item.imported_by_user_id),
                "activated_by_username": users_by_id.get(item.activated_by_user_id),
                "total_items": counts.get(item.id, 0),
            }
        )
    return rows


def create_library_import(
    db: Session,
    *,
    label: str,
    import_method: str,
    imported_by_user_id: int,
    bgg_ids: list[int],
    activate: bool,
) -> models.LibraryImport:
    if not bgg_ids:
        raise ValueError("Import must contain at least one BGG ID.")

    existing = (
        db.query(models.LibraryImport)
        .filter(func.lower(models.LibraryImport.label) == label.lower())
        .first()
    )
    if existing is not None:
        raise ValueError("Import label already exists.")

    now = datetime.utcnow()
    library_import = models.LibraryImport(
        label=label,
        import_method=import_method,
        imported_by_user_id=imported_by_user_id,
        is_active=False,
        created_at=now,
    )
    db.add(library_import)
    db.flush()

    if bgg_ids:
        for index in range(0, len(bgg_ids), LIBRARY_IMPORT_INSERT_BATCH_SIZE):
            batch_ids = bgg_ids[index : index + LIBRARY_IMPORT_INSERT_BATCH_SIZE]
            db.execute(
                insert(models.LibraryImportItem),
                [
                    {"library_import_id": library_import.id, "bgg_id": bgg_id}
                    for bgg_id in batch_ids
                ],
            )

    if activate:
        db.query(models.LibraryImport).filter(
            models.LibraryImport.is_active.is_(True)
        ).update(
            {
                models.LibraryImport.is_active: False,
                models.LibraryImport.activated_by_user_id: None,
                models.LibraryImport.activated_at: None,
            },
            synchronize_session=False,
        )
        library_import.is_active = True
        library_import.activated_by_user_id = imported_by_user_id
        library_import.activated_at = now

    db.commit()
    clear_total_count_cache()
    db.refresh(library_import)
    return library_import


def activate_library_import(
    db: Session, *, import_id: int, activated_by_user_id: int
) -> Optional[models.LibraryImport]:
    library_import = (
        db.query(models.LibraryImport)
        .filter(models.LibraryImport.id == import_id)
        .first()
    )
    if library_import is None:
        return None

    now = datetime.utcnow()
    db.query(models.LibraryImport).filter(
        models.LibraryImport.is_active.is_(True)
    ).update(
        {
            models.LibraryImport.is_active: False,
            models.LibraryImport.activated_by_user_id: None,
            models.LibraryImport.activated_at: None,
        },
        synchronize_session=False,
    )
    library_import.is_active = True
    library_import.activated_by_user_id = activated_by_user_id
    library_import.activated_at = now
    db.commit()
    clear_total_count_cache()
    db.refresh(library_import)
    return library_import


def delete_library_import(db: Session, *, import_id: int) -> bool:
    library_import = (
        db.query(models.LibraryImport)
        .filter(models.LibraryImport.id == import_id)
        .with_for_update()
        .first()
    )
    if library_import is None:
        return False
    if library_import.is_active:
        raise ValueError("Active library import cannot be deleted.")

    db.query(models.LibraryImportItem).filter(
        models.LibraryImportItem.library_import_id == library_import.id
    ).delete(synchronize_session=False)
    deleted_import_count = (
        db.query(models.LibraryImport)
        .filter(
            models.LibraryImport.id == library_import.id,
            models.LibraryImport.is_active.is_(False),
        )
        .delete(synchronize_session=False)
    )
    if deleted_import_count != 1:
        db.rollback()
        raise ValueError("Active library import cannot be deleted.")
    db.commit()
    return True


def find_missing_games_for_ids(db: Session, bgg_ids: list[int]) -> list[int]:
    if not bgg_ids:
        return []
    rows = db.query(models.BoardGame.id).filter(models.BoardGame.id.in_(bgg_ids)).all()
    existing = {row[0] for row in rows}
    return [bgg_id for bgg_id in bgg_ids if bgg_id not in existing]
