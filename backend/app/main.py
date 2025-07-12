from fastapi import FastAPI, HTTPException, Request, Depends, status, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse, RedirectResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from typing import List, Optional
import logging
import httpx
from sqlalchemy.orm import Session
from pathlib import Path
from . import crud, models, schemas, recommender, security
from .database import engine, SessionLocal, CORSAwareStaticFiles
import time
from functools import lru_cache
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import os
# import sys
from pathlib import Path
from fastapi import APIRouter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create database tables
models.Base.metadata.create_all(bind=engine)

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent
# Define images directory for local development
IMAGES_DIR = PROJECT_ROOT / "backend" / "database" / "images"
STATIC_DIR = PROJECT_ROOT / "frontend" / "build"

app = FastAPI(
    title="Board Game Recommender API",
    description="API for board game recommendations and filtering",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Gzip compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Mount images directory for local development with CORS support
if os.path.exists(IMAGES_DIR):
    logger.info(f"Mounting images directory from {IMAGES_DIR}")
    app.mount("/images", CORSAwareStaticFiles(directory=str(IMAGES_DIR)), name="images")
else:
    logger.warning(f"Images directory not found at {IMAGES_DIR}")

# # Serve static frontend files
# if os.path.exists(STATIC_DIR):
#     logger.info(f"Mounting React frontend from {STATIC_DIR}")
#     app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="frontend")
# else:
#     logger.warning(f"Frontend build directory not found at {STATIC_DIR}")

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTP error: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred"}
    )

# Simple in-memory cache for frequently accessed data
_cache = {}
_cache_ttl = {}

def get_cached_data(key: str, ttl_seconds: int = 300):
    """Get data from cache if not expired."""
    if key in _cache and key in _cache_ttl:
        if time.time() < _cache_ttl[key]:
            return _cache[key]
        else:
            # Remove expired cache entry
            del _cache[key]
            del _cache_ttl[key]
    return None

def set_cached_data(key: str, data, ttl_seconds: int = 300):
    """Set data in cache with TTL."""
    _cache[key] = data
    _cache_ttl[key] = time.time() + ttl_seconds

# Thread pool for database operations
db_executor = ThreadPoolExecutor(max_workers=4)

async def run_with_timeout(func, *args, timeout_seconds=25, **kwargs):
    """Run a function with a timeout to prevent hanging."""
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            db_executor, 
            lambda: func(*args, **kwargs)
        )
        return result
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Request timeout")
    except Exception as e:
        logger.error(f"Database operation error: {str(e)}")
        raise HTTPException(status_code=500, detail="Database error")

@app.get("/api")
async def api_root():
    return {"message": "Board Game Recommender API"}

# Move the root endpoint to /api and keep this as a fallback for API requests
@app.get("/", include_in_schema=False)
async def root(request: Request):
    # If the Accept header indicates API request, return API response
    accept_header = request.headers.get("accept", "")
    if "application/json" in accept_header:
        return {"message": "Board Game Recommender API"}
    
    # Otherwise, serve the frontend index.html
    if os.path.exists(STATIC_DIR / "index.html"):
        return FileResponse(STATIC_DIR / "index.html")
    else:
        return {"message": "Board Game Recommender API"}

# Keep the proxy-image endpoint for compatibility with development environment
@app.get("/api/proxy-image/{url:path}")
async def proxy_image(url: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch image")
            
            return StreamingResponse(
                response.iter_bytes(),
                media_type=response.headers.get("content-type", "image/jpeg"),
                headers={
                    "Cache-Control": "public, max-age=31536000",
                    "Access-Control-Allow-Origin": "*"
                }
            )
    except Exception as e:
        logger.error(f"Error proxying image {url}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching image")

@app.get("/api/games/", response_model=schemas.GameListResponse)
async def list_games(
    db: Session = Depends(get_db),
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
        # Direct call - no thread pool overhead for better performance
        # With proper indexes, queries should be fast enough
        games, total = crud.get_games(
            db=db,
            skip=skip,
            limit=limit,
            sort_by=sort_by,
            search=search,
            players=players,
            designer_id=designer_id,
            artist_id=artist_id,
            recommendations=recommendations,
            weight=weight,
            mechanics=mechanics,
            categories=categories,
            pax_only=pax_only
        )
        return {"games": games, "total": total}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching games: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching games")

@app.get("/api/games/{game_id}", response_model=schemas.BoardGameOut)
@app.get("/api/games/{game_id}/", response_model=schemas.BoardGameOut)  # Add endpoint with trailing slash
async def get_game(game_id: int, db: Session = Depends(get_db)):
    try:
        game = crud.get_game(db, game_id)
        if game is None:
            raise HTTPException(status_code=404, detail="Game not found")
        return game
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching game {game_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching game")

@app.get("/api/recommendations/{game_id}", response_model=List[schemas.BoardGameOut])
@app.get("/api/recommendations/{game_id}/", response_model=List[schemas.BoardGameOut])  # Add endpoint with trailing slash
async def get_recommendations(
    game_id: int,
    db: Session = Depends(get_db),
    limit: int = 10,
    disliked_games: Optional[str] = None,
    anti_weight: float = 1.0,
    pax_only: Optional[bool] = False
):
    """
    Get game recommendations based on a game ID.
    
    Args:
        game_id: ID of the game to get recommendations for
        db: Database session
        limit: Maximum number of recommendations to return
        disliked_games: Comma-separated list of game IDs to use as anti-recommendations
        anti_weight: Weight to apply to anti-recommendations (higher values = stronger anti-recommendations)
        pax_only: If true, only recommend games that are in the PAX games table
    """
    try:
        # Parse disliked games if provided
        disliked_games_list = None
        if disliked_games:
            try:
                disliked_games_list = [int(gid) for gid in disliked_games.split(',')]
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid disliked_games format. Expected comma-separated list of game IDs."
                )
        
        recommendations = crud.get_recommendations(
            db=db,
            limit=limit,
            liked_games=[game_id],
            disliked_games=disliked_games_list,
            anti_weight=anti_weight,
            pax_only=pax_only
        )
        return recommendations
    except Exception as e:
        logger.error(f"Error getting recommendations for game {game_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error getting recommendations")

@app.get("/api/filter-options/", response_model=schemas.FilterOptions)
async def get_filter_options(db: Session = Depends(get_db)):
    try:
        # Check cache first
        cache_key = "filter_options"
        cached_result = get_cached_data(cache_key, ttl_seconds=1800)  # 30 minutes cache
        if cached_result:
            return cached_result
        
        # Get from database
        options = crud.get_filter_options(db)
        
        # Cache the result
        set_cached_data(cache_key, options, ttl_seconds=1800)
        
        return options
    except Exception as e:
        logger.error(f"Error fetching filter options: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching filter options")

@app.get("/api/mechanics/", response_model=List[schemas.MechanicBase])
async def list_mechanics(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
):
    try:
        # Check cache first
        cache_key = f"mechanics_{skip}_{limit}"
        cached_result = get_cached_data(cache_key, ttl_seconds=600)  # 10 minutes cache
        if cached_result:
            return cached_result
        
        # Get from database
        mechanics = crud.get_mechanics_cached(db, skip=skip, limit=limit)
        
        # Cache the result
        set_cached_data(cache_key, mechanics, ttl_seconds=600)
        
        return mechanics
    except Exception as e:
        logger.error(f"Error fetching mechanics: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching mechanics")

@app.get("/api/pax_games/with_board_game_links")
def read_pax_games_with_board_game_links(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_pax_games_with_board_game_links(db=db, skip=skip, limit=limit)

@app.get("/api/mechanics/by_frequency", response_model=List[schemas.MechanicFrequency])
def read_mechanics_by_frequency(db: Session = Depends(get_db)):
    return crud.get_mechanics_by_frequency(db=db)

@app.get("/api/categories/by_frequency", response_model=List[schemas.CategoryFrequency])
def read_categories_by_frequency(db: Session = Depends(get_db)):
    return crud.get_categories_by_frequency(db=db)

@app.get("/api/categories", response_model=List[schemas.Category])
def read_categories(db: Session = Depends(get_db)):
    categories = crud.get_categories_cached(db)
    return categories

@app.get("/api/pax_game_ids", response_model=List[int])
@app.get("/api/pax_game_ids/", response_model=List[int])  # Add endpoint with trailing slash
async def get_pax_game_ids(db: Session = Depends(get_db)):
    """Return a list of all PAX game BGG IDs (integers)."""
    pax_ids = db.query(models.PAXGame.bgg_id).filter(models.PAXGame.bgg_id.isnot(None)).all()
    # pax_ids is a list of tuples, extract the first element from each
    return [pid[0] for pid in pax_ids if pid[0] is not None]

@app.on_event("startup")
async def startup_event():
    """Load the recommender model on startup."""
    logger.info("Loading recommender model...")
    recommender.ModelManager.get_instance().load_model()

class RecommendationRequest(schemas.BaseModel):
    liked_games: Optional[List[int]] = None
    disliked_games: Optional[List[int]] = None
    limit: int = 24
    anti_weight: float = 1.0
    pax_only: bool = False

@app.post("/api/recommendations", response_model=List[schemas.BoardGameOut])
async def get_multi_game_recommendations(
    request: RecommendationRequest,
    db: Session = Depends(get_db)
):
    """
    Get game recommendations based on a list of liked and disliked games.
    No authentication required beyond being able to access the site.
    """
    try:
        recommendations = crud.get_recommendations(
            db=db,
            limit=request.limit,
            liked_games=request.liked_games,
            disliked_games=request.disliked_games,
            anti_weight=request.anti_weight,
            pax_only=request.pax_only
        )
        return recommendations
    except Exception as e:
        logger.error(f"Error getting recommendations: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error getting recommendations")

# Add a direct token endpoint at the root level
@app.post("/token", response_model=schemas.Token)
async def login_for_access_token_root(db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    """Legacy token endpoint for backward compatibility"""
    user = crud.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# --- User and Auth Endpoints ---

@app.post("/api/token", response_model=schemas.Token)
async def login_for_access_token(db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    user = crud.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}
    

@app.post("/api/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db), current_user: schemas.User = Depends(security.get_current_active_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only admin users can create new users.")
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    return crud.create_user(db=db, user=user)

@app.get("/api/users/me/", response_model=schemas.User)
async def read_users_me(current_user: schemas.User = Depends(security.get_current_active_user)):
    return current_user


# Serve static frontend files
if os.path.exists(STATIC_DIR):
    logger.info(f"Mounting React frontend from {STATIC_DIR}")
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="frontend")
else:
    logger.warning(f"Frontend build directory not found at {STATIC_DIR}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Create initial admin user.")
    parser.add_argument("--username", required=True, help="Admin username")
    parser.add_argument("--password", required=True, help="Admin password")
    args = parser.parse_args()
    security.create_initial_admin(args.username, args.password)

