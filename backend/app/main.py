from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    Request,
    Depends,
    status,
    Response,
    Header,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import (
    JSONResponse,
    StreamingResponse,
    FileResponse,
    RedirectResponse,
)
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from typing import List, Literal, Optional
import logging
import httpx
import hmac
import mimetypes
import tempfile
from urllib.parse import quote
from sqlalchemy.orm import Session
from pathlib import Path
from . import crud, models, schemas, recommender, security
from . import convention_kiosk
from .database import (
    engine,
    SessionLocal,
    CORSAwareStaticFiles,
    SQLALCHEMY_DATABASE_URL,
)
from .db_keepalive import (
    resolve_keepalive_interval_seconds,
    run_db_keepalive_loop,
    should_enable_db_keepalive,
    stop_keepalive_task,
)
from .image_processing import build_thumbnail_relative_path, write_webp_thumbnail
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import os
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from .logging_utils import build_log_handlers
from .versioning import get_app_version

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=build_log_handlers("app.log"),
)
logger = logging.getLogger(__name__)

# Create database tables
models.Base.metadata.create_all(bind=engine)

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent
# Define images directory (local default, Fly override via IMAGE_STORAGE_DIR)
IMAGE_STORAGE_DIR = Path(
    os.getenv(
        "IMAGE_STORAGE_DIR",
        str(PROJECT_ROOT / "backend" / "database" / "images"),
    )
)
STATIC_DIR = PROJECT_ROOT / "frontend" / "build"

app = FastAPI(
    title="Board Game Recommender API",
    description="API for board game recommendations and filtering",
    version=get_app_version(),
)

GameSortField = Literal[
    "rank",
    "abstracts_rank",
    "cgs_rank",
    "childrens_games_rank",
    "family_games_rank",
    "party_games_rank",
    "strategy_games_rank",
    "thematic_rank",
    "wargames_rank",
    "name_asc",
    "name_desc",
    "recommendation_score",
]

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif", "avif"}
CONTENT_TYPE_TO_EXTENSION = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/avif": "avif",
}


class KioskEnrollRequest(BaseModel):
    kiosk_key: Optional[str] = None


def apply_recommendation_status_headers(response: Response) -> None:
    """Expose recommendation availability so the UI can distinguish degraded mode."""
    for key, value in get_recommendation_status_headers().items():
        response.headers[key] = value


def get_recommendation_status_headers() -> dict[str, str]:
    """Build recommendation availability headers for success and error paths."""
    model_status = recommender.ModelManager.get_instance().get_status()
    return {
        "X-Recommendations-Available": (
            "true" if model_status["available"] else "false"
        ),
        "X-Recommendations-State": model_status["state"],
    }


def apply_recommendation_status_to_http_exception(
    exc: HTTPException,
) -> HTTPException:
    """Ensure recommendation state headers survive exception responses."""
    headers = dict(exc.headers or {})
    headers.update(get_recommendation_status_headers())
    exc.headers = headers
    return exc


def get_cors_origins() -> List[str]:
    """Resolve CORS origins from env with safe defaults."""
    env_value = os.getenv("CORS_ALLOWED_ORIGINS", "")
    node_env = os.getenv("NODE_ENV", "development").lower()

    if env_value.strip():
        origins = [origin.strip() for origin in env_value.split(",") if origin.strip()]
    elif node_env == "production":
        # Production defaults to explicit origins only (no wildcard).
        origins = [
            "https://pax-tt-app.fly.dev",
            "https://pax-tt-app-dev.fly.dev",
        ]
    else:
        origins = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]

    if node_env == "production" and ("*" in origins or not origins):
        raise RuntimeError(
            "Invalid production CORS configuration. "
            "Set explicit CORS_ALLOWED_ORIGINS (comma-separated)."
        )
    return origins


# Resolve CORS config once at startup so invalid production config fails fast.
cors_origins = get_cors_origins()
logger.info("Configured CORS origins: %s", cors_origins)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Gzip compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Mount images directory with CORS support
try:
    IMAGE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Mounting images directory from %s", IMAGE_STORAGE_DIR)
    app.mount(
        "/images",
        CORSAwareStaticFiles(directory=str(IMAGE_STORAGE_DIR)),
        name="images",
    )
except Exception as exc:  # pragma: no cover - startup safety logging
    logger.warning("Failed to mount images directory %s: %s", IMAGE_STORAGE_DIR, exc)

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
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTP error: {exc.detail}")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500, content={"detail": "An unexpected error occurred"}
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
_db_keepalive_task: asyncio.Task | None = None
_db_keepalive_stop_event: asyncio.Event | None = None


async def run_with_timeout(func, *args, timeout_seconds=25, **kwargs):
    """Run a function with a timeout to prevent hanging."""
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(db_executor, lambda: func(*args, **kwargs))
        return result
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Request timeout")
    except Exception as e:
        logger.error(f"Database operation error: {str(e)}")
        raise HTTPException(status_code=500, detail="Database error")


def get_r2_public_base_url() -> str | None:
    """Return configured public CDN base URL for image delivery, if present."""
    return os.getenv("R2_PUBLIC_BASE_URL", "").strip().rstrip("/") or None


def infer_extension_from_content_type(content_type: str | None) -> str | None:
    if not content_type:
        return None
    media_type = content_type.split(";", 1)[0].strip().lower()
    return CONTENT_TYPE_TO_EXTENSION.get(media_type)


def infer_extension_from_url(image_url: str | None) -> str | None:
    if not image_url:
        return None
    guessed_type, _ = mimetypes.guess_type(image_url)
    if guessed_type:
        extension = infer_extension_from_content_type(guessed_type)
        if extension:
            return extension
    filename = image_url.split("?", 1)[0].split("#", 1)[0].rsplit("/", 1)[-1]
    if "." not in filename:
        return None
    extension = filename.rsplit(".", 1)[-1].lower()
    if extension in ALLOWED_IMAGE_EXTENSIONS:
        return "jpg" if extension == "jpeg" else extension
    return None


def build_image_storage_relative_path(
    game_id: int,
    *,
    image_url: str | None = None,
    content_type: str | None = None,
) -> str:
    extension = (
        infer_extension_from_content_type(content_type)
        or infer_extension_from_url(image_url)
        or "jpg"
    )
    return f"games/{game_id}.{extension}"


@retry(
    retry=retry_if_exception_type(httpx.HTTPError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
async def download_origin_image_content(
    image_url: str,
    *,
    timeout_seconds: int = 20,
) -> tuple[bytes, str | None]:
    async with httpx.AsyncClient() as client:
        response = await client.get(image_url, timeout=timeout_seconds)
        response.raise_for_status()
        return response.content, response.headers.get("Content-Type")


def get_image_backend() -> str:
    """Return active image backend mode."""
    return os.getenv("IMAGE_BACKEND", "bgg_proxy").strip().lower()


def find_existing_local_image_relative_path(game_id: int) -> str | None:
    for extension in sorted(ALLOWED_IMAGE_EXTENSIONS):
        normalized_ext = "jpg" if extension == "jpeg" else extension
        relative_path = f"games/{game_id}.{normalized_ext}"
        if (IMAGE_STORAGE_DIR / relative_path).exists():
            return relative_path
    return None


def persist_cached_image_bundle(
    *,
    image_bytes: bytes,
    destination: Path,
    thumbnail_destination: Path,
) -> None:
    """
    Persist original image and thumbnail to local storage.

    Intended to run in a worker thread from async request handlers.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=str(destination.parent),
        prefix=f"{destination.name}.",
        suffix=".tmp",
        delete=False,
    ) as tmp_file:
        tmp_file.write(image_bytes)
        tmp_name = tmp_file.name
    Path(tmp_name).replace(destination)

    write_webp_thumbnail(
        image_bytes,
        thumbnail_destination,
    )


async def run_image_io_task(task):
    """Run blocking image I/O task outside the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(db_executor, task)


@app.get("/api")
async def api_root():
    return {"message": "Board Game Recommender API"}


@app.get("/api/version")
async def api_version():
    """Return runtime build metadata for release traceability."""
    return {
        "app_version": app.version,
        "git_sha": os.getenv("APP_GIT_SHA", "unknown"),
        "build_timestamp": os.getenv("APP_BUILD_TIMESTAMP", "unknown"),
        "environment": os.getenv("NODE_ENV", "development"),
        "convention_mode": os.getenv("CONVENTION_MODE", "false").strip().lower()
        == "true",
    }


@app.get("/api/convention/kiosk/status")
async def convention_kiosk_status(request: Request):
    convention_mode = convention_kiosk.is_convention_mode_enabled()
    kiosk_mode = False

    if convention_mode:
        cookie_token = request.cookies.get(convention_kiosk.KIOSK_COOKIE_NAME)
        kiosk_mode = convention_kiosk.is_valid_kiosk_cookie_token(
            token=cookie_token,
            secret_key=security.SECRET_KEY,
            algorithm=security.ALGORITHM,
        )

    return {
        "convention_mode": convention_mode,
        "kiosk_mode": kiosk_mode,
    }


@app.post("/api/convention/kiosk/enroll")
async def convention_kiosk_enroll(
    response: Response,
    payload: KioskEnrollRequest,
    x_convention_kiosk_key: Optional[str] = Header(default=None),
):
    if (
        not convention_kiosk.is_convention_mode_enabled()
        or not convention_kiosk.is_convention_guest_enabled()
    ):
        raise HTTPException(
            status_code=404, detail="Convention kiosk enrollment is disabled."
        )

    expected_key = convention_kiosk.get_expected_kiosk_key()
    if not expected_key:
        raise HTTPException(
            status_code=503, detail="Convention kiosk key is not configured."
        )

    provided_key = (payload.kiosk_key or x_convention_kiosk_key or "").strip()
    if not provided_key or not hmac.compare_digest(provided_key, expected_key):
        raise HTTPException(status_code=401, detail="Invalid kiosk key.")

    kiosk_token = convention_kiosk.issue_kiosk_cookie_token(
        secret_key=security.SECRET_KEY,
        algorithm=security.ALGORITHM,
    )
    response.set_cookie(
        key=convention_kiosk.KIOSK_COOKIE_NAME,
        value=kiosk_token,
        max_age=convention_kiosk.KIOSK_COOKIE_TTL_SECONDS,
        httponly=True,
        secure=os.getenv("NODE_ENV", "development").lower() == "production",
        samesite="lax",
        path="/",
    )

    return {
        "convention_mode": True,
        "kiosk_mode": True,
        "expires_in": convention_kiosk.KIOSK_COOKIE_TTL_SECONDS,
    }


@app.post("/api/convention/kiosk/unenroll")
async def convention_kiosk_unenroll(response: Response):
    response.delete_cookie(
        key=convention_kiosk.KIOSK_COOKIE_NAME,
        path="/",
    )
    return {"kiosk_mode": False}


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
                raise HTTPException(
                    status_code=response.status_code, detail="Failed to fetch image"
                )

            return StreamingResponse(
                response.iter_bytes(),
                media_type=response.headers.get("content-type", "image/jpeg"),
                headers={
                    "Cache-Control": "public, max-age=31536000",
                    "Access-Control-Allow-Origin": "*",
                },
            )
    except Exception as e:
        logger.error(f"Error proxying image {url}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching image")


@app.get("/api/images/{game_id}/cached")
async def get_cached_image(
    game_id: int,
    image_url: Optional[str] = Query(default=None),
):
    """
    Resolve an image by game ID using the configured backend.

    - `fly_local`: redirect to mounted local files and cache-fill from origin on misses.
    - `r2_cdn`: redirect to configured public CDN key path.
    - fallback/unknown: proxy origin image.
    """
    resolved_image_url = (image_url or "").strip()
    if not resolved_image_url:
        db = SessionLocal()
        try:
            game = crud.get_game(db, game_id)
            if game is None or not game.image:
                raise HTTPException(status_code=404, detail="Game image not found")
            resolved_image_url = game.image
        finally:
            db.close()

    image_backend = get_image_backend()

    if image_backend == "fly_local":
        try:
            existing_relative_path = find_existing_local_image_relative_path(game_id)
            if existing_relative_path:
                return RedirectResponse(
                    url=f"/images/{existing_relative_path}",
                    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                )

            image_bytes, content_type = await download_origin_image_content(
                resolved_image_url
            )
            relative_path = build_image_storage_relative_path(
                game_id,
                image_url=resolved_image_url,
                content_type=content_type,
            )
            destination = IMAGE_STORAGE_DIR / relative_path
            thumbnail_destination = IMAGE_STORAGE_DIR / build_thumbnail_relative_path(
                game_id
            )
            await run_image_io_task(
                lambda: persist_cached_image_bundle(
                    image_bytes=image_bytes,
                    destination=destination,
                    thumbnail_destination=thumbnail_destination,
                )
            )
            return RedirectResponse(
                url=f"/images/{relative_path}",
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            )
        except Exception as exc:  # pragma: no cover - defensive fallback path
            logger.warning(
                "Fly-local image cache-fill failed for game_id=%s image=%s; falling back to proxy. Error: %s",
                game_id,
                resolved_image_url,
                exc,
            )
            return RedirectResponse(
                url=f"/api/proxy-image/{quote(resolved_image_url, safe='')}",
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            )

    if image_backend == "r2_cdn":
        r2_public_base_url = get_r2_public_base_url()
        if r2_public_base_url:
            key = build_image_storage_relative_path(
                game_id, image_url=resolved_image_url
            )
            return RedirectResponse(
                url=f"{r2_public_base_url}/{key}",
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            )

    try:  # Fallback for bgg_proxy or unknown backend values
        return RedirectResponse(
            url=f"/api/proxy-image/{quote(resolved_image_url, safe='')}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )
    except Exception:  # pragma: no cover - defensive fallback path
        return RedirectResponse(
            url=f"/api/proxy-image/{quote(resolved_image_url, safe='')}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )


@app.get("/api/games/", response_model=schemas.GameListResponse)
async def list_games(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(24, ge=1, le=100),
    sort_by: GameSortField = "rank",
    search: Optional[str] = None,
    players: Optional[int] = Query(None, ge=1, le=12),
    designer_id: Optional[str] = None,
    artist_id: Optional[str] = None,
    recommendations: Optional[str] = None,
    weight: Optional[str] = None,
    mechanics: Optional[str] = None,
    categories: Optional[str] = None,
    pax_only: Optional[bool] = False,
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
            pax_only=pax_only,
        )
        return {"games": games, "total": total}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching games: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching games")


@app.get("/api/games/{game_id}", response_model=schemas.BoardGameOut)
@app.get(
    "/api/games/{game_id}/", response_model=schemas.BoardGameOut
)  # Add endpoint with trailing slash
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


@app.get(
    "/api/recommendations/{game_id}", response_model=List[schemas.RecommendationGameOut]
)
@app.get(
    "/api/recommendations/{game_id}/",
    response_model=List[schemas.RecommendationGameOut],
)  # Add endpoint with trailing slash
async def get_recommendations(
    game_id: int,
    response: Response,
    db: Session = Depends(get_db),
    limit: int = Query(10, ge=1, le=50),
    disliked_games: Optional[str] = None,
    anti_weight: float = Query(1.0, gt=0),
    pax_only: Optional[bool] = False,
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
                disliked_games_list = [int(gid) for gid in disliked_games.split(",")]
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid disliked_games format. Expected comma-separated list of game IDs.",
                )

        recommendations = crud.get_recommendations(
            db=db,
            limit=limit,
            liked_games=[game_id],
            disliked_games=disliked_games_list,
            anti_weight=anti_weight,
            pax_only=pax_only,
        )
        apply_recommendation_status_headers(response)
        return recommendations
    except HTTPException as exc:
        raise apply_recommendation_status_to_http_exception(exc)
    except Exception as e:
        logger.error(
            f"Error getting recommendations for game {game_id}: {str(e)}", exc_info=True
        )
        raise apply_recommendation_status_to_http_exception(
            HTTPException(status_code=500, detail="Error getting recommendations")
        )


@app.get("/api/recommendations/status")
@app.get("/api/recommendations/status/")
async def get_recommendation_status(response: Response):
    """Return whether recommendation artifacts are currently available."""
    model_status = recommender.ModelManager.get_instance().get_status()
    apply_recommendation_status_headers(response)
    return model_status


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
    db: Session = Depends(get_db), skip: int = 0, limit: int = 500
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
def read_pax_games_with_board_game_links(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    return crud.get_pax_games_with_board_game_links(db=db, skip=skip, limit=limit)


@app.get("/api/mechanics/by_frequency", response_model=List[schemas.MechanicFrequency])
def read_mechanics_by_frequency(db: Session = Depends(get_db)):
    return crud.get_mechanics_by_frequency(db=db)


@app.get("/api/categories/by_frequency", response_model=List[schemas.CategoryFrequency])
def read_categories_by_frequency(db: Session = Depends(get_db)):
    return crud.get_categories_by_frequency(db=db)


@app.get("/api/categories/", response_model=List[schemas.CategoryBase])
def read_categories(db: Session = Depends(get_db)):
    categories = crud.get_categories_cached(db)
    return categories


@app.get("/api/pax_game_ids", response_model=List[int])
@app.get(
    "/api/pax_game_ids/", response_model=List[int]
)  # Add endpoint with trailing slash
async def get_pax_game_ids(db: Session = Depends(get_db)):
    """Return a list of all PAX game BGG IDs (integers)."""
    pax_ids = (
        db.query(models.PAXGame.bgg_id).filter(models.PAXGame.bgg_id.isnot(None)).all()
    )
    # pax_ids is a list of tuples, extract the first element from each
    return [pid[0] for pid in pax_ids if pid[0] is not None]


@app.on_event("startup")
async def startup_event():
    """Load the recommender model on startup."""
    global _db_keepalive_task, _db_keepalive_stop_event
    logger.info("Loading recommender model...")
    try:
        recommender.ModelManager.get_instance().load_model()
    except FileNotFoundError as exc:
        logger.error(
            "Recommendation model unavailable at startup: %s. "
            "The app will stay up, but recommendations will return empty results.",
            exc,
        )
    except Exception as exc:
        logger.error(
            "Recommendation model failed to load at startup: %s. "
            "The app will stay up, but recommendations may be unavailable.",
            exc,
            exc_info=True,
        )
    if should_enable_db_keepalive(SQLALCHEMY_DATABASE_URL):
        interval_seconds = resolve_keepalive_interval_seconds()
        _db_keepalive_stop_event = asyncio.Event()
        _db_keepalive_task = asyncio.create_task(
            run_db_keepalive_loop(
                engine=engine,
                interval_seconds=interval_seconds,
                stop_event=_db_keepalive_stop_event,
            )
        )
        logger.info(
            "DB keepalive enabled (interval=%ss).",
            interval_seconds,
        )
    else:
        logger.info("DB keepalive disabled for current database/runtime configuration.")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    global _db_keepalive_task, _db_keepalive_stop_event
    await stop_keepalive_task(_db_keepalive_task, _db_keepalive_stop_event)
    _db_keepalive_task = None
    _db_keepalive_stop_event = None


class RecommendationRequest(schemas.BaseModel):
    liked_games: Optional[List[int]] = None
    disliked_games: Optional[List[int]] = None
    limit: int = schemas.Field(24, ge=1, le=50)
    anti_weight: float = schemas.Field(1.0, gt=0)
    pax_only: bool = False


@app.post("/api/recommendations", response_model=List[schemas.RecommendationGameOut])
async def get_multi_game_recommendations(
    request: RecommendationRequest, response: Response, db: Session = Depends(get_db)
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
            pax_only=request.pax_only,
        )
        apply_recommendation_status_headers(response)
        return recommendations
    except HTTPException as exc:
        raise apply_recommendation_status_to_http_exception(exc)
    except Exception as e:
        logger.error(f"Error getting recommendations: {str(e)}", exc_info=True)
        raise apply_recommendation_status_to_http_exception(
            HTTPException(status_code=500, detail="Error getting recommendations")
        )


# Add a direct token endpoint at the root level
@app.post("/token", response_model=schemas.Token)
async def login_for_access_token_root(
    db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
):
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
async def login_for_access_token(
    db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
):
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
def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(security.get_current_active_user),
):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403, detail="Only admin users can create new users."
        )
    db_user = crud.get_user_by_username(db, username=user.username.lower())
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    return crud.create_user(db=db, user=user)


@app.get("/api/users/me/", response_model=schemas.User)
async def read_users_me(
    current_user: schemas.User = Depends(security.get_current_active_user),
):
    return current_user


@app.put("/api/users/me/password", response_model=schemas.PasswordChangeResponse)
def change_password(
    password_request: schemas.PasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(security.get_current_active_user),
):
    success = crud.change_user_password(
        db=db,
        user_id=current_user.id,
        old_password=password_request.current_password,
        new_password=password_request.new_password,
    )
    if not success:
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    return schemas.PasswordChangeResponse(message="Password changed successfully")


@app.post("/api/suggestions/", response_model=schemas.UserSuggestionResponse)
def create_suggestion(
    suggestion: schemas.UserSuggestionCreate,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(security.get_current_active_user),
):
    logger.info(
        "Creating suggestion for user_id=%s username=%s",
        current_user.id,
        current_user.username,
    )
    db_suggestion = crud.create_user_suggestion(
        db=db, user_id=current_user.id, suggestion=suggestion
    )
    logger.info(
        "Created suggestion id=%s for user_id=%s",
        db_suggestion.id,
        current_user.id,
    )
    return schemas.UserSuggestionResponse(
        id=db_suggestion.id,
        comment=db_suggestion.comment,
        timestamp=db_suggestion.timestamp.isoformat(),
        username=current_user.username,
    )


# Serve static frontend files
if os.path.exists(STATIC_DIR):
    logger.info(f"Mounting React frontend from {STATIC_DIR}")
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="frontend")
else:
    logger.warning(f"Frontend build directory not found at {STATIC_DIR}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Create user account.")
    parser.add_argument("--username", required=True, help="Username")
    parser.add_argument("--password", required=True, help="Password")
    parser.add_argument(
        "--admin",
        action="store_true",
        help="Create as admin user (default: regular user)",
    )
    parser.add_argument(
        "--reset-password", action="store_true", help="Reset password for existing user"
    )
    args = parser.parse_args()

    if args.reset_password:
        security.reset_password_cli(args.username, args.password)
    else:
        security.create_user_cli(args.username, args.password, args.admin)
