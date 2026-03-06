import threading
import time
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import exists, func, select
from sqlalchemy.sql import or_, and_
from . import models, schemas, security
from typing import Any, List, Optional
import logging

logger = logging.getLogger(__name__)

_TOTAL_CACHE_LOCK = threading.Lock()
_TOTAL_CACHE_TTL_SECONDS = 120
_TOTAL_CACHE_MAX_ENTRIES = 128
_total_count_cache: dict[tuple[Any, ...], tuple[float, int]] = {}


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
    pax_only: Optional[bool],
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
        bool(pax_only),
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
    pax_only: Optional[bool] = False
):
    try:
        # Start with a base query - only load main game fields initially
        query = db.query(models.BoardGame)

        if sort_by == 'recommendation_score':
            sort_by = 'rank'

        if pax_only:
            query = query.filter(
                exists().where(models.PAXGame.bgg_id == models.BoardGame.id)
            )

        # Apply simple filters first
        if search:
            search_term = f"%{search}%"
            query = query.filter(models.BoardGame.name.ilike(search_term))

        if weight:
            weight_list = weight.split(',')
            weight_conditions = []
            if 'beginner' in weight_list:
                weight_conditions.append(models.BoardGame.average_weight <= 2.0)
            if 'midweight' in weight_list:
                weight_conditions.append(and_(
                    models.BoardGame.average_weight > 2.0,
                    models.BoardGame.average_weight < 4.0
                ))
            if 'heavy' in weight_list:
                weight_conditions.append(models.BoardGame.average_weight >= 4.0)
            
            if weight_conditions:
                query = query.filter(or_(*weight_conditions))

        # Apply relationship filters using efficient subqueries with timeout protection
        if designer_id:
            try:
                designer_ids = [int(d_id) for d_id in designer_id.split(',')]
                subquery = select(models.BoardGame.id).join(
                    models.BoardGame.designers
                ).filter(
                    models.Designer.boardgamedesigner_id.in_(designer_ids)
                ).group_by(
                    models.BoardGame.id
                ).having(
                    func.count(models.Designer.boardgamedesigner_id) == len(designer_ids)
                ).subquery()
                query = query.filter(models.BoardGame.id.in_(subquery))
            except Exception as e:
                logger.warning(f"Error applying designer filter: {str(e)}")
                # Continue without designer filter if it fails

        if artist_id:
            try:
                artist_ids = [int(a_id) for a_id in artist_id.split(',')]
                subquery = select(models.BoardGame.id).join(
                    models.BoardGame.artists
                ).filter(
                    models.Artist.boardgameartist_id.in_(artist_ids)
                ).group_by(
                    models.BoardGame.id
                ).having(
                    func.count(models.Artist.boardgameartist_id) == len(artist_ids)
                ).subquery()
                query = query.filter(models.BoardGame.id.in_(subquery))
            except Exception as e:
                logger.warning(f"Error applying artist filter: {str(e)}")
                # Continue without artist filter if it fails

        if mechanics:
            try:
                mechanic_ids = [int(m_id) for m_id in mechanics.split(',')]
                subquery = select(models.BoardGame.id).join(
                    models.BoardGame.mechanics
                ).filter(
                    models.Mechanic.boardgamemechanic_id.in_(mechanic_ids)
                ).group_by(
                    models.BoardGame.id
                ).having(
                    func.count(models.Mechanic.boardgamemechanic_id) == len(mechanic_ids)
                ).subquery()
                query = query.filter(models.BoardGame.id.in_(subquery))
            except Exception as e:
                logger.warning(f"Error applying mechanics filter: {str(e)}")
                # Continue without mechanics filter if it fails

        if categories:
            try:
                category_ids = [int(c_id) for c_id in categories.split(',')]
                subquery = select(models.BoardGame.id).join(
                    models.BoardGame.categories
                ).filter(
                    models.Category.boardgamecategory_id.in_(category_ids)
                ).group_by(
                    models.BoardGame.id
                ).having(
                    func.count(models.Category.boardgamecategory_id) == len(category_ids)
                ).subquery()
                query = query.filter(models.BoardGame.id.in_(subquery))
            except Exception as e:
                logger.warning(f"Error applying categories filter: {str(e)}")
                # Continue without categories filter if it fails

        if recommendations:
            try:
                rec_list = recommendations.split(',')
                # Need to join with suggested_players table for recommendations filter
                query = query.join(models.BoardGame.suggested_players)
                if players:
                    query = query.filter(models.SuggestedPlayer.player_count == players)
                if 'best' in rec_list:
                    query = query.filter(
                        models.SuggestedPlayer.recommendation_level == 'best'
                    )
                if 'recommended' in rec_list:
                    query = query.filter(
                        models.SuggestedPlayer.recommendation_level == 'recommended'
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
                        models.BoardGame.max_players >= players
                    )
                )
            except Exception as e:
                logger.warning(f"Error applying players filter: {str(e)}")
                # Continue without players filter if it fails

        # Verify that the sort_by field exists in the model, or handle special cases
        if sort_by.startswith("name_"):
            order_field = "name"
            order_dir = sort_by.split('_')[1]
        elif hasattr(models.BoardGame, sort_by):
            order_field = sort_by
            order_dir = "asc"
        else:
            raise ValueError(f"Invalid sort field: {sort_by}")

        # Order by the selected field, with NULLs last
        rank_field = getattr(models.BoardGame, order_field)
        if order_dir == 'desc':
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
            pax_only=pax_only,
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
    db_game = models.BoardGame(**game.dict(exclude={'mechanics', 'categories', 'designers', 'artists', 'publishers'}))
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
        "publishers": [p[0] for p in publishers]
    }

def get_mechanics_cached(db: Session, skip: int = 0, limit: int = 100):
    """Get mechanics with pagination and caching-friendly structure."""
    mechanics = db.query(
        models.Mechanic.boardgamemechanic_id,
        models.Mechanic.boardgamemechanic_name
    ).distinct().order_by(
        models.Mechanic.boardgamemechanic_name
    ).offset(skip).limit(limit).all()
    
    return [{"boardgamemechanic_id": m[0], "boardgamemechanic_name": m[1]} for m in mechanics]

def get_categories_cached(db: Session, skip: int = 0, limit: int = 100):
    """Get categories with pagination and caching-friendly structure."""
    categories = db.query(
        models.Category.boardgamecategory_id,
        models.Category.boardgamecategory_name
    ).distinct().order_by(
        models.Category.boardgamecategory_name
    ).offset(skip).limit(limit).all()

    return [{"boardgamecategory_id": c[0], "boardgamecategory_name": c[1]} for c in categories]

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
    return db.query(
        models.Mechanic.boardgamemechanic_id,
        models.Mechanic.boardgamemechanic_name, 
        func.count(models.Mechanic.game_id).label('frequency')
    ).group_by(
        models.Mechanic.boardgamemechanic_id,
        models.Mechanic.boardgamemechanic_name
    ).order_by(
        func.count(models.Mechanic.game_id).desc()
    ).all()

def get_categories_by_frequency(db: Session):
    return db.query(
        models.Category.boardgamecategory_id,
        models.Category.boardgamecategory_name,
        func.count(models.Category.boardgamecategory_id).label('frequency')
    ).group_by(
        models.Category.boardgamecategory_id,
        models.Category.boardgamecategory_name
    ).order_by(
        func.count(models.Category.boardgamecategory_id).desc()
    ).all()

def get_recommendations(
    db: Session,
    limit: int = 20,
    liked_games: Optional[List[int]] = None,
    disliked_games: Optional[List[int]] = None,
    anti_weight: float = 1.0,
    pax_only: Optional[bool] = False
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
        pax_only=pax_only
    )

# PAX Games CRUD operations
def get_pax_games(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    convention_name: Optional[str] = None,
    convention_year: Optional[int] = None,
    has_bgg_id: Optional[bool] = None
):
    """Get PAX games with optional filtering."""
    query = db.query(models.PAXGame)
    
    if convention_name:
        query = query.filter(models.PAXGame.convention_name == convention_name)
    
    if convention_year:
        query = query.filter(models.PAXGame.convention_year == convention_year)
    
    if has_bgg_id is not None:
        if has_bgg_id:
            query = query.filter(models.PAXGame.bgg_id.isnot(None))
        else:
            query = query.filter(models.PAXGame.bgg_id.is_(None))
    
    # Get total count before pagination
    total = query.count()
    
    # Apply pagination
    pax_games = query.offset(skip).limit(limit).all()
    
    return pax_games, total


def get_pax_game(db: Session, pax_game_id: int):
    """Get a specific PAX game by ID."""
    return db.query(models.PAXGame).filter(models.PAXGame.id == pax_game_id).first()


def get_pax_game_by_bgg_id(db: Session, bgg_id: int):
    """Get PAX game by BGG ID."""
    return db.query(models.PAXGame).filter(models.PAXGame.bgg_id == bgg_id).first()


def create_pax_game(db: Session, pax_game: schemas.PAXGameCreate):
    """Create a new PAX game."""
    db_pax_game = models.PAXGame(**pax_game.model_dump())
    db.add(db_pax_game)
    db.commit()
    db.refresh(db_pax_game)
    return db_pax_game


def get_pax_games_by_convention(db: Session, convention_name: str, convention_year: Optional[int] = None):
    """Get PAX games for a specific convention."""
    query = db.query(models.PAXGame).filter(models.PAXGame.convention_name == convention_name)
    
    if convention_year:
        query = query.filter(models.PAXGame.convention_year == convention_year)
    
    return query.all()


def get_pax_games_with_board_game_links(db: Session, skip: int = 0, limit: int = 100):
    """Get PAX games that have links to BoardGame records."""
    query = db.query(models.PAXGame).filter(models.PAXGame.bgg_id.isnot(None))
    
    # Get total count before pagination
    total = query.count()
    
    # Apply pagination
    pax_games = query.offset(skip).limit(limit).all()
    
    return pax_games, total

def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(func.lower(models.User.username) == username.lower()).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = security.get_password_hash(user.password)
    db_user = models.User(
        username=user.username.lower(),
        hashed_password=hashed_password,
        is_admin=user.is_admin if hasattr(user, 'is_admin') else False
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

def create_user_suggestion(db: Session, user_id: int, suggestion: schemas.UserSuggestionCreate):
    db_suggestion = models.UserSuggestion(
        user_id=user_id,
        comment=suggestion.comment
    )
    db.add(db_suggestion)
    db.commit()
    db.refresh(db_suggestion)
    return db_suggestion

def change_user_password(db: Session, user_id: int, old_password: str, new_password: str):
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
