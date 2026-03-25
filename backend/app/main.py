from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    Request,
    Depends,
    status,
    Response,
    File,
    Form,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
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
import csv
import io
import httpx
import mimetypes
import tempfile
import ipaddress
import socket
import sys
from collections import deque
from getpass import getpass
from urllib.parse import quote
from urllib.parse import urlsplit
from uuid import uuid4
from sqlalchemy.orm import Session
from sqlalchemy import text
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
from datetime import datetime, timedelta
import os
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

# Ensure base tables exist for local/test SQLite execution paths.
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


class SPAStaticFiles(StaticFiles):
    """Serve index.html for client-side routes while preserving API 404 behavior."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise

            request_path = scope.get("path", "")
            is_api_or_system_path = request_path.startswith(
                ("/api", "/health", "/openapi", "/docs", "/redoc")
            )
            has_file_extension = "." in Path(request_path).name

            if is_api_or_system_path or has_file_extension:
                raise

            return await super().get_response("index.html", scope)


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
MAX_PROXY_IMAGE_BYTES = 10 * 1024 * 1024
MAX_LIBRARY_IMPORT_CSV_BYTES = 2 * 1024 * 1024
RATE_LIMIT_WINDOW_SECONDS = 60
THEME_PRIMARY_COLOR_SETTING_KEY = "theme_primary_color"
LIBRARY_NAME_SETTING_KEY = "library_name"
RECOMMENDER_COLLABORATIVE_WEIGHT_SETTING_KEY = "recommender_collaborative_weight"
RECOMMENDER_CONTENT_WEIGHT_SETTING_KEY = "recommender_content_weight"
RECOMMENDER_QUALITY_WEIGHT_SETTING_KEY = "recommender_quality_weight"
DEFAULT_THEME_PRIMARY_COLOR = "#D9272D"
CATALOG_REFRESH_TRIGGERED_AT_SETTING_KEY = "catalog_refresh_triggered_at"


class InMemoryRateLimiter:
    """Simple process-local fixed-window rate limiter."""

    def __init__(self, window_seconds: int = RATE_LIMIT_WINDOW_SECONDS):
        self.window_seconds = window_seconds
        self._bucket: dict[str, deque[float]] = {}

    def allow(self, *, key: str, limit: int) -> bool:
        now = time.monotonic()
        window_start = now - self.window_seconds
        bucket = self._bucket.setdefault(key, deque())
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    API_CSP = (
        "default-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'none'; "
        "form-action 'none'"
    )
    FRONTEND_CSP = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https:; "
        "font-src 'self' data:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.path.startswith("/api/"):
            csp_value = os.getenv("API_CSP", self.API_CSP).strip()
        else:
            csp_value = os.getenv("FRONTEND_CSP", self.FRONTEND_CSP).strip()
        if csp_value:
            response.headers.setdefault("Content-Security-Policy", csp_value)
        if os.getenv("NODE_ENV", "development").lower() == "production":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply endpoint-class rate limits using client IP and path."""

    def __init__(self, app, limiter: InMemoryRateLimiter):
        super().__init__(app)
        self._limiter = limiter

    @staticmethod
    def _read_limit(env_key: str, default: int) -> int:
        raw_value = os.getenv(env_key, "").strip()
        if not raw_value:
            return default
        try:
            value = int(raw_value)
        except ValueError:
            return default
        return value if value > 0 else default

    @classmethod
    def _resolve_limit(cls, path: str) -> int | None:
        if path in {"/api/token", "/token"}:
            return cls._read_limit("RATE_LIMIT_AUTH_PER_MIN", 10)
        if path.startswith("/api/recommendations"):
            return cls._read_limit("RATE_LIMIT_RECOMMENDATIONS_PER_MIN", 120)
        if path.startswith("/api/"):
            return cls._read_limit("RATE_LIMIT_API_PER_MIN", 300)
        return None

    @staticmethod
    def _is_truthy_env(value: str) -> bool:
        return value.strip().lower() in {"1", "true", "yes", "on"}

    def _client_key(self, request: Request, path: str) -> str:
        client_ip = ""
        trust_forwarded_for = self._is_truthy_env(
            os.getenv("TRUST_X_FORWARDED_FOR", "false")
        )
        if trust_forwarded_for:
            forwarded_for = request.headers.get("x-forwarded-for", "")
            client_ip = forwarded_for.split(",", 1)[0].strip() if forwarded_for else ""
        if not client_ip:
            client = request.client
            client_ip = client.host if client else "unknown"
        return f"{path}|{client_ip}"

    async def dispatch(self, request: Request, call_next):
        if not self._is_truthy_env(os.getenv("RATE_LIMIT_ENABLED", "true")):
            return await call_next(request)

        path = request.url.path
        limit = self._resolve_limit(path)
        if limit is None:
            return await call_next(request)

        key = self._client_key(request, path)
        if not self._limiter.allow(key=key, limit=limit):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please try again later."},
            )
        return await call_next(request)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach request ID context and propagate it in response headers."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", "").strip() or uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers.setdefault("X-Request-ID", request_id)
        return response


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Log request timing with request ID for operational observability."""

    async def dispatch(self, request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - started) * 1000
        request_id = getattr(request.state, "request_id", "unknown")
        logger.info(
            "request_completed request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        response.headers.setdefault("X-Response-Time-Ms", f"{duration_ms:.2f}")
        return response


def _is_disallowed_ip_address(ip_text: str) -> bool:
    try:
        address = ipaddress.ip_address(ip_text)
    except ValueError:
        return True
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def _is_disallowed_host(host: str) -> bool:
    normalized_host = host.strip().lower().rstrip(".")
    if not normalized_host:
        return True
    if normalized_host in {"localhost", "metadata.google.internal"}:
        return True

    try:
        ipaddress.ip_address(normalized_host)
    except ValueError:
        return False
    return _is_disallowed_ip_address(normalized_host)


def validate_proxy_image_url(raw_url: str) -> str:
    parsed = urlsplit(raw_url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(
            status_code=400,
            detail="Invalid image URL scheme. Only http/https are allowed.",
        )
    if parsed.username or parsed.password:
        raise HTTPException(
            status_code=400,
            detail="Image URL must not include credentials.",
        )

    host = parsed.hostname
    if host is None or _is_disallowed_host(host):
        raise HTTPException(status_code=400, detail="Invalid image URL host.")

    port = parsed.port
    try:
        addrinfos = socket.getaddrinfo(
            host,
            port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except OSError:
        raise HTTPException(
            status_code=400, detail="Image URL host could not be resolved."
        )

    for addrinfo in addrinfos:
        ip_text = addrinfo[4][0]
        if _is_disallowed_ip_address(ip_text):
            raise HTTPException(
                status_code=400, detail="Image URL host is not allowed."
            )

    return raw_url


def resolve_cli_password(
    *,
    password_arg: Optional[str],
    use_stdin: bool,
) -> str:
    if password_arg:
        return password_arg
    if use_stdin:
        password = sys.stdin.readline().rstrip("\r\n")
        if not password:
            raise ValueError("Password from stdin is empty.")
        return password

    password = getpass("Password: ")
    confirm = getpass("Confirm Password: ")
    if password != confirm:
        raise ValueError("Passwords do not match.")
    if not password:
        raise ValueError("Password is empty.")
    return password


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
        "X-Recommendations-Collaborative-Available": (
            "true" if model_status.get("collaborative_available") else "false"
        ),
        "X-Recommendations-Content-Available": (
            "true" if model_status.get("content_available") else "false"
        ),
        "X-Recommendations-Hybrid-Available": (
            "true" if model_status.get("hybrid_available") else "false"
        ),
    }


def _get_non_negative_float_setting(
    db: Session,
    *,
    key: str,
    fallback: float,
    minimum: float = 0.0,
    maximum: float = 1.0,
) -> float:
    try:
        setting = crud.get_app_setting(db, key)
    except AttributeError:
        return fallback
    if setting is None or setting.value is None:
        return fallback
    try:
        parsed = float(setting.value)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid float app setting for key=%s value=%s", key, setting.value
        )
        return fallback
    if parsed < minimum or parsed > maximum:
        logger.warning(
            "Out-of-range app setting for key=%s value=%s expected_range=[%s,%s]",
            key,
            setting.value,
            minimum,
            maximum,
        )
        return fallback
    return parsed


def _get_global_recommender_weights(db: Session) -> tuple[float, float, float]:
    defaults = recommender.HYBRID_SCORING_CONFIG
    collaborative_weight = _get_non_negative_float_setting(
        db,
        key=RECOMMENDER_COLLABORATIVE_WEIGHT_SETTING_KEY,
        fallback=defaults.collaborative_weight,
    )
    content_weight = _get_non_negative_float_setting(
        db,
        key=RECOMMENDER_CONTENT_WEIGHT_SETTING_KEY,
        fallback=defaults.content_weight,
    )
    quality_weight = _get_non_negative_float_setting(
        db,
        key=RECOMMENDER_QUALITY_WEIGHT_SETTING_KEY,
        fallback=defaults.quality_weight,
    )
    return (collaborative_weight, content_weight, quality_weight)


def _resolve_recommender_weight_overrides(
    *,
    db: Session,
    collaborative_weight: float | None,
    content_weight: float | None,
    quality_weight: float | None,
) -> tuple[float, float, float]:
    (
        global_collaborative_weight,
        global_content_weight,
        global_quality_weight,
    ) = _get_global_recommender_weights(db)
    return (
        collaborative_weight
        if collaborative_weight is not None
        else global_collaborative_weight,
        content_weight if content_weight is not None else global_content_weight,
        quality_weight if quality_weight is not None else global_quality_weight,
    )


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
        prod_app_name = os.getenv("FLY_APP_NAME_PROD", "").strip()
        dev_app_name = os.getenv("FLY_APP_NAME_DEV", "").strip()
        # Production defaults to explicit origins only (no wildcard).
        origins = []
        if prod_app_name:
            origins.append(f"https://{prod_app_name}.fly.dev")
        if dev_app_name:
            origins.append(f"https://{dev_app_name}.fly.dev")
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


def validate_startup_config() -> None:
    """Fail fast on invalid startup env values."""

    def _validate_optional_positive_int_env(
        name: str, *, minimum: int = 1, maximum: int | None = None
    ) -> None:
        raw_value = os.getenv(name, "").strip()
        if not raw_value:
            return
        try:
            value = int(raw_value)
        except ValueError as exc:
            raise RuntimeError(f"{name} must be an integer.") from exc
        if value < minimum:
            raise RuntimeError(f"{name} must be >= {minimum}.")
        if maximum is not None and value > maximum:
            raise RuntimeError(f"{name} must be <= {maximum}.")

    def _validate_optional_bool_env(name: str) -> None:
        raw_value = os.getenv(name, "").strip()
        if not raw_value:
            return
        normalized = raw_value.lower()
        allowed = {"1", "0", "true", "false", "yes", "no", "on", "off"}
        if normalized not in allowed:
            raise RuntimeError(
                f"{name} must be a boolean-like value: 1/0/true/false/yes/no/on/off."
            )

    _validate_optional_positive_int_env("RATE_LIMIT_AUTH_PER_MIN", minimum=1)
    _validate_optional_positive_int_env("RATE_LIMIT_RECOMMENDATIONS_PER_MIN", minimum=1)
    _validate_optional_positive_int_env("RATE_LIMIT_API_PER_MIN", minimum=1)
    _validate_optional_positive_int_env("DB_KEEPALIVE_INTERVAL_SECONDS", minimum=5)

    _validate_optional_bool_env("RATE_LIMIT_ENABLED")
    _validate_optional_bool_env("TRUST_X_FORWARDED_FOR")
    _validate_optional_bool_env("DB_KEEPALIVE_ENABLED")
    _validate_optional_bool_env("CONVENTION_MODE")
    _validate_optional_bool_env("CONVENTION_GUEST_ENABLED")

    if (
        convention_kiosk.is_convention_mode_enabled()
        and not os.getenv("CONVENTION_GUEST_ENABLED", "").strip()
    ):
        raise RuntimeError(
            "CONVENTION_GUEST_ENABLED must be explicitly set when CONVENTION_MODE is enabled."
        )


# Validate startup config once so invalid values fail before serving traffic.
validate_startup_config()

# Resolve CORS config once at startup so invalid production config fails fast.
cors_origins = get_cors_origins()
logger.info("Configured CORS origins: %s", cors_origins)
RATE_LIMITER = InMemoryRateLimiter()

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
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, limiter=RATE_LIMITER)
app.add_middleware(RequestTimingMiddleware)
app.add_middleware(RequestContextMiddleware)

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
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


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


@app.get("/api/catalog/state", response_model=schemas.CatalogStateResponse)
def api_catalog_state(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    active_import = crud.get_active_library_import(db)
    total_games = crud.get_games_count(db)
    app_version = app.version
    git_sha = os.getenv("APP_GIT_SHA", "unknown")
    build_timestamp = os.getenv("APP_BUILD_TIMESTAMP", "unknown")
    active_library_import_id = active_import.id if active_import else None
    active_library_activated_at = active_import.activated_at if active_import else None
    activated_at_token = (
        active_library_activated_at.isoformat()
        if active_library_activated_at
        else "none"
    )
    state_token = (
        f"lib:{active_library_import_id or 'none'}|"
        f"activated:{activated_at_token}|"
        f"games:{total_games}|"
        f"sha:{git_sha}|"
        f"build:{build_timestamp}"
    )

    return schemas.CatalogStateResponse(
        active_library_import_id=active_library_import_id,
        active_library_activated_at=active_library_activated_at,
        total_games=total_games,
        app_version=app_version,
        git_sha=git_sha,
        build_timestamp=build_timestamp,
        state_token=state_token,
    )


def check_db_readiness() -> tuple[bool, str | None]:
    """Check whether the DB is reachable for request serving."""
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:  # pragma: no cover - defensive runtime guard
        return False, str(exc)
    finally:
        db.close()


def get_model_readiness() -> dict[str, str | bool]:
    """Expose recommendation model readiness state for health checks."""
    status_payload = recommender.ModelManager.get_instance().get_status()
    return {
        "available": bool(status_payload.get("available", False)),
        "state": str(status_payload.get("state", "unknown")),
    }


@app.get("/health/live")
async def health_live():
    return {"status": "live"}


@app.get("/health/ready")
async def health_ready():
    db_ready, db_error = check_db_readiness()
    model_status = get_model_readiness()
    model_state = str(model_status.get("state", "unknown"))
    model_ready = bool(model_status.get("available")) or model_state in {
        "degraded",
        "missing_artifacts",
        "corrupt_artifacts",
    }
    ready = db_ready and model_ready

    payload = {
        "status": "ready" if ready else "not_ready",
        "checks": {
            "database": {"ready": db_ready, "error": db_error},
            "model": {
                "ready": model_ready,
                "available": bool(model_status.get("available")),
                "state": model_state,
            },
        },
    }
    if not ready:
        return JSONResponse(status_code=503, content=payload)
    return payload


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


def _ensure_convention_kiosk_enrollment_enabled() -> None:
    if (
        not convention_kiosk.is_convention_mode_enabled()
        or not convention_kiosk.is_convention_guest_enabled()
    ):
        raise HTTPException(
            status_code=404, detail="Convention kiosk enrollment is disabled."
        )


def _set_kiosk_cookie(response: Response) -> None:
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


def _require_admin(current_user: schemas.User) -> None:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required.")


def _analyze_library_csv(raw_bytes: bytes) -> dict[str, object]:
    if not raw_bytes:
        raise ValueError("CSV file is empty.")

    try:
        decoded = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8 encoded.") from exc

    rows = [
        row
        for row in csv.reader(io.StringIO(decoded))
        if any(cell.strip() for cell in row)
    ]
    if not rows:
        raise ValueError("CSV file is empty.")

    first_row = [cell.strip() for cell in rows[0]]
    has_header = any(cell.lower() == "bgg_id" for cell in first_row)
    bgg_col_index = 0
    if has_header:
        for index, value in enumerate(first_row):
            if value.lower() == "bgg_id":
                bgg_col_index = index
                break
        data_rows = rows[1:]
    else:
        data_rows = rows

    parsed_rows: list[tuple[int, int]] = []
    invalid_warnings: list[dict[str, object]] = []
    for row_number, row in enumerate(data_rows, start=(2 if has_header else 1)):
        if bgg_col_index >= len(row):
            continue
        raw_value = row[bgg_col_index].strip()
        if not raw_value:
            continue
        if not raw_value.isdigit():
            invalid_warnings.append(
                {
                    "row_number": row_number,
                    "value": raw_value,
                    "reason": "not_positive_integer",
                }
            )
            continue
        parsed_value = int(raw_value)
        if parsed_value <= 0:
            invalid_warnings.append(
                {
                    "row_number": row_number,
                    "value": raw_value,
                    "reason": "not_positive_integer",
                }
            )
            continue
        parsed_rows.append((row_number, parsed_value))

    if not parsed_rows and not invalid_warnings:
        raise ValueError("CSV did not contain any valid bgg_id values.")

    seen: set[int] = set()
    deduped_rows: list[tuple[int, int]] = []
    duplicate_rows = 0
    for row_number, parsed_value in parsed_rows:
        if parsed_value in seen:
            duplicate_rows += 1
            continue
        seen.add(parsed_value)
        deduped_rows.append((row_number, parsed_value))

    if not deduped_rows:
        raise ValueError("CSV did not contain any valid bgg_id values.")

    return {
        "total_rows": len(data_rows),
        "parsed_rows": parsed_rows,
        "deduped_rows": deduped_rows,
        "duplicate_rows": duplicate_rows,
        "invalid_warnings": invalid_warnings,
    }


@app.post("/api/convention/kiosk/admin/enroll")
async def convention_kiosk_enroll_admin(
    response: Response,
    current_user: schemas.User = Depends(security.get_current_active_user),
):
    _require_admin(current_user)
    _ensure_convention_kiosk_enrollment_enabled()
    _set_kiosk_cookie(response)
    return {
        "convention_mode": True,
        "kiosk_mode": True,
        "expires_in": convention_kiosk.KIOSK_COOKIE_TTL_SECONDS,
    }


@app.post("/api/convention/kiosk/admin/unenroll")
async def convention_kiosk_unenroll_admin(
    response: Response,
    current_user: schemas.User = Depends(security.get_current_active_user),
):
    _require_admin(current_user)
    response.delete_cookie(
        key=convention_kiosk.KIOSK_COOKIE_NAME,
        path="/",
    )
    return {"kiosk_mode": False}


@app.post("/api/convention/guest-token", response_model=schemas.Token)
async def issue_convention_guest_token(request: Request):
    _ensure_convention_kiosk_enrollment_enabled()

    cookie_token = request.cookies.get(convention_kiosk.KIOSK_COOKIE_NAME)
    if not convention_kiosk.is_valid_kiosk_cookie_token(
        token=cookie_token,
        secret_key=security.SECRET_KEY,
        algorithm=security.ALGORITHM,
    ):
        raise HTTPException(status_code=401, detail="Kiosk enrollment is required.")

    access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={
            "sub": security.CONVENTION_GUEST_USERNAME,
            "token_type": security.CONVENTION_GUEST_TOKEN_TYPE,
        },
        expires_delta=access_token_expires,
    )
    return {"access_token": access_token, "token_type": "bearer"}


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
        validated_url = validate_proxy_image_url(url)
        async with httpx.AsyncClient() as client:
            response = await client.get(
                validated_url, follow_redirects=False, timeout=20.0
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code, detail="Failed to fetch image"
                )
            content_length = response.headers.get("content-length")
            if content_length is not None:
                try:
                    if int(content_length) > MAX_PROXY_IMAGE_BYTES:
                        raise HTTPException(
                            status_code=413, detail="Image is too large."
                        )
                except ValueError:
                    pass

            return StreamingResponse(
                response.iter_bytes(),
                media_type=response.headers.get("content-type", "image/jpeg"),
                headers={
                    "Cache-Control": "public, max-age=31536000",
                    "Access-Control-Allow-Origin": "*",
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error proxying image request: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching image")


@app.get("/api/images/{game_id}/cached")
async def get_cached_image(
    game_id: int,
    image_url: Optional[str] = Query(default=None),
):
    """
    Resolve an image by game ID using the configured backend.

    - `fly_local`: redirect to mounted local files and cache-fill from origin on misses.
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
    response: Response,
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
    library_only: Optional[bool] = False,
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
            library_only=library_only,
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
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


@app.get("/api/recommendations/status")
@app.get("/api/recommendations/status/")
async def get_recommendation_status(response: Response):
    """Return whether recommendation artifacts are currently available."""
    model_status = recommender.ModelManager.get_instance().get_status()
    apply_recommendation_status_headers(response)
    return model_status


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
    library_only: Optional[bool] = False,
    recommender_mode: Literal["collaborative", "hybrid"] = Query("hybrid"),
    collaborative_weight: float | None = Query(default=None),
    content_weight: float | None = Query(default=None),
    quality_weight: float | None = Query(default=None),
):
    """
    Get game recommendations based on a game ID.

    Args:
        game_id: ID of the game to get recommendations for
        db: Database session
        limit: Maximum number of recommendations to return
        disliked_games: Comma-separated list of game IDs to use as anti-recommendations
        anti_weight: Weight to apply to anti-recommendations (higher values = stronger anti-recommendations)
        library_only: If true, only recommend games from the active library import
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

        (
            resolved_collaborative_weight,
            resolved_content_weight,
            resolved_quality_weight,
        ) = _resolve_recommender_weight_overrides(
            db=db,
            collaborative_weight=collaborative_weight,
            content_weight=content_weight,
            quality_weight=quality_weight,
        )

        recommendations = crud.get_recommendations(
            db=db,
            limit=limit,
            liked_games=[game_id],
            disliked_games=disliked_games_list,
            anti_weight=anti_weight,
            library_only=library_only,
            recommender_mode=recommender_mode,
            collaborative_weight=resolved_collaborative_weight,
            content_weight=resolved_content_weight,
            quality_weight=resolved_quality_weight,
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


@app.get("/api/library_game_ids", response_model=List[int])
@app.get(
    "/api/library_game_ids/", response_model=List[int]
)  # Add endpoint with trailing slash
async def get_library_game_ids(response: Response, db: Session = Depends(get_db)):
    """Return a list of all Library game BGG IDs (integers)."""
    # This endpoint reflects mutable admin state; avoid intermediary caches.
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return crud.get_library_ids_for_runtime(db)


@app.on_event("startup")
async def startup_event():
    """Load recommender artifacts on startup."""
    global _db_keepalive_task, _db_keepalive_stop_event
    logger.info("Loading recommender artifacts...")
    model_manager = recommender.ModelManager.get_instance()
    try:
        model_manager.load_model()
    except FileNotFoundError as exc:
        logger.error(
            "Collaborative recommendation embeddings unavailable at startup: %s. "
            "The app will stay up, but recommendations will return empty results.",
            exc,
        )
    except Exception as exc:
        logger.error(
            "Collaborative recommendation embeddings failed to load at startup: %s. "
            "The app will stay up, but recommendations may be unavailable.",
            exc,
            exc_info=True,
        )
    try:
        model_manager.load_content_model()
    except FileNotFoundError as exc:
        logger.warning(
            "Hybrid content embeddings unavailable at startup: %s. "
            "Hybrid mode will fall back to collaborative+quality scoring.",
            exc,
        )
    except Exception as exc:
        logger.warning(
            "Hybrid content embeddings failed to load at startup: %s. "
            "Hybrid mode will fall back to collaborative+quality scoring.",
            exc,
            exc_info=True,
        )

    startup_status = model_manager.get_status()
    logger.info(
        "Recommender artifact readiness: collaborative_available=%s content_available=%s hybrid_available=%s",
        startup_status.get("collaborative_available"),
        startup_status.get("content_available"),
        startup_status.get("hybrid_available"),
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
    library_only: bool = False
    recommender_mode: Literal["collaborative", "hybrid"] = "hybrid"
    collaborative_weight: float | None = None
    content_weight: float | None = None
    quality_weight: float | None = None


@app.post("/api/recommendations", response_model=List[schemas.RecommendationGameOut])
async def get_multi_game_recommendations(
    request: RecommendationRequest, response: Response, db: Session = Depends(get_db)
):
    """
    Get game recommendations based on a list of liked and disliked games.
    No authentication required beyond being able to access the site.
    """
    try:
        (
            resolved_collaborative_weight,
            resolved_content_weight,
            resolved_quality_weight,
        ) = _resolve_recommender_weight_overrides(
            db=db,
            collaborative_weight=request.collaborative_weight,
            content_weight=request.content_weight,
            quality_weight=request.quality_weight,
        )

        recommendations = crud.get_recommendations(
            db=db,
            limit=request.limit,
            liked_games=request.liked_games,
            disliked_games=request.disliked_games,
            anti_weight=request.anti_weight,
            library_only=request.library_only,
            recommender_mode=request.recommender_mode,
            collaborative_weight=resolved_collaborative_weight,
            content_weight=resolved_content_weight,
            quality_weight=resolved_quality_weight,
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


@app.get("/api/admin/users", response_model=list[schemas.AdminUser])
def list_admin_users(
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(security.get_current_active_user),
):
    _require_admin(current_user)
    users = crud.get_users(db)
    return [
        schemas.AdminUser(
            id=user.id,
            username=user.username,
            is_active=user.is_active,
            is_admin=user.is_admin,
        )
        for user in users
    ]


@app.put("/api/admin/users/{user_id}", response_model=schemas.AdminUser)
def update_admin_user(
    user_id: int,
    request: schemas.AdminUserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(security.get_current_active_user),
):
    _require_admin(current_user)

    target_user = crud.get_user(db, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    if target_user.id == current_user.id:
        if request.is_active is False:
            raise HTTPException(
                status_code=400, detail="You cannot deactivate your own account."
            )
        if request.is_admin is False:
            raise HTTPException(
                status_code=400, detail="You cannot remove your own admin access."
            )

    updated_user = crud.update_user_admin_flags(
        db,
        user_id=user_id,
        is_admin=request.is_admin,
        is_active=request.is_active,
    )
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    return schemas.AdminUser(
        id=updated_user.id,
        username=updated_user.username,
        is_active=updated_user.is_active,
        is_admin=updated_user.is_admin,
    )


@app.put(
    "/api/admin/users/{user_id}/password", response_model=schemas.PasswordChangeResponse
)
def admin_reset_user_password(
    user_id: int,
    request: schemas.AdminUserPasswordResetRequest,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(security.get_current_active_user),
):
    _require_admin(current_user)
    success = crud.admin_reset_password_by_user_id(
        db=db,
        user_id=user_id,
        new_password=request.new_password,
    )
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return schemas.PasswordChangeResponse(message="Password reset successfully")


@app.get(
    "/api/admin/library-imports", response_model=list[schemas.LibraryImportSummary]
)
def list_admin_library_imports(
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(security.get_current_active_user),
):
    _require_admin(current_user)
    rows = crud.list_library_import_summaries(db)
    return [schemas.LibraryImportSummary(**row) for row in rows]


def _build_csv_validation_result(
    *,
    analysis: dict[str, object],
    missing_ids: list[int],
) -> schemas.LibraryImportCsvValidationResponse:
    missing_set = set(missing_ids)
    deduped_rows = analysis["deduped_rows"]
    unknown_warnings = [
        {
            "row_number": row_number,
            "value": str(bgg_id),
            "reason": "id_not_in_games_catalog",
        }
        for row_number, bgg_id in deduped_rows
        if bgg_id in missing_set
    ]
    return schemas.LibraryImportCsvValidationResponse(
        total_rows=int(analysis["total_rows"]),
        valid_rows=len(deduped_rows),
        duplicate_rows=int(analysis["duplicate_rows"]),
        invalid_rows=len(analysis["invalid_warnings"]),
        unknown_id_rows=len(unknown_warnings),
        unique_candidate_ids=len(deduped_rows),
        warnings_invalid_rows=[
            schemas.LibraryImportCsvWarning(**item)
            for item in analysis["invalid_warnings"]
        ],
        warnings_unknown_ids=[
            schemas.LibraryImportCsvWarning(**item) for item in unknown_warnings
        ],
    )


async def _read_upload_with_size_limit(
    file: UploadFile,
    *,
    max_bytes: int,
    chunk_size: int = 64 * 1024,
) -> bytes:
    await file.seek(0)
    chunks: list[bytes] = []
    total_bytes = 0

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > max_bytes:
            raise HTTPException(
                status_code=400,
                detail="CSV is too large. Maximum size is 2MB.",
            )
        chunks.append(chunk)

    return b"".join(chunks)


@app.post(
    "/api/admin/library-imports/csv/validate",
    response_model=schemas.LibraryImportCsvValidationResponse,
)
async def validate_admin_library_import_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(security.get_current_active_user),
):
    _require_admin(current_user)

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv uploads are supported.")

    file_payload = await _read_upload_with_size_limit(
        file, max_bytes=MAX_LIBRARY_IMPORT_CSV_BYTES
    )

    try:
        analysis = _analyze_library_csv(file_payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    deduped_ids = [bgg_id for _, bgg_id in analysis["deduped_rows"]]
    missing_ids = crud.find_missing_games_for_ids(db, deduped_ids)
    return _build_csv_validation_result(analysis=analysis, missing_ids=missing_ids)


@app.post(
    "/api/admin/library-imports/csv",
    response_model=schemas.LibraryImportUploadResponse,
)
async def upload_admin_library_import_csv(
    label: str = Form(..., min_length=1, max_length=120),
    file: UploadFile = File(...),
    activate: bool = Form(True),
    ignore_invalid_rows: bool = Form(True),
    allow_unknown_ids: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(security.get_current_active_user),
):
    _require_admin(current_user)

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv uploads are supported.")

    file_payload = await _read_upload_with_size_limit(
        file, max_bytes=MAX_LIBRARY_IMPORT_CSV_BYTES
    )

    try:
        analysis = _analyze_library_csv(file_payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    deduped_rows = analysis["deduped_rows"]
    deduped_ids = [bgg_id for _, bgg_id in deduped_rows]
    skipped_duplicates = int(analysis["duplicate_rows"])
    skipped_invalid_rows = len(analysis["invalid_warnings"])
    if skipped_invalid_rows > 0 and not ignore_invalid_rows:
        raise HTTPException(
            status_code=400,
            detail=(
                "CSV contains invalid bgg_id rows. Run validation first or set "
                "ignore_invalid_rows=true to continue while skipping them."
            ),
        )

    missing_ids = crud.find_missing_games_for_ids(db, deduped_ids)
    missing_set = set(missing_ids)
    kept_unknown_ids = 0
    skipped_unknown_ids = 0
    selected_ids: list[int] = []
    for bgg_id in deduped_ids:
        if bgg_id in missing_set:
            if allow_unknown_ids:
                kept_unknown_ids += 1
                selected_ids.append(bgg_id)
            else:
                skipped_unknown_ids += 1
        else:
            selected_ids.append(bgg_id)

    if skipped_unknown_ids > 0 and not allow_unknown_ids and not selected_ids:
        raise HTTPException(
            status_code=400,
            detail=(
                "All IDs were unknown to the games catalog. Enable allow_unknown_ids "
                "to include them."
            ),
        )
    if not selected_ids:
        raise HTTPException(
            status_code=400, detail="No IDs left to import after applying filters."
        )

    clean_label = label.strip()
    if not clean_label:
        raise HTTPException(status_code=400, detail="Label is required.")

    try:
        import_record = crud.create_library_import(
            db,
            label=clean_label,
            import_method="csv_upload",
            imported_by_user_id=current_user.id,
            bgg_ids=selected_ids,
            activate=activate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    rows = crud.list_library_import_summaries(db)
    summary_row = next((row for row in rows if row["id"] == import_record.id), None)
    if summary_row is None:
        raise HTTPException(status_code=500, detail="Failed to read import summary.")

    return schemas.LibraryImportUploadResponse(
        import_record=schemas.LibraryImportSummary(**summary_row),
        skipped_duplicates=skipped_duplicates,
        skipped_invalid_rows=skipped_invalid_rows,
        skipped_unknown_ids=skipped_unknown_ids,
        kept_unknown_ids=kept_unknown_ids,
    )


@app.post(
    "/api/admin/library-imports/{import_id}/activate",
    response_model=schemas.LibraryImportSummary,
)
def activate_admin_library_import(
    import_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(security.get_current_active_user),
):
    _require_admin(current_user)
    updated = crud.activate_library_import(
        db, import_id=import_id, activated_by_user_id=current_user.id
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Library import not found")

    rows = crud.list_library_import_summaries(db)
    summary_row = next((row for row in rows if row["id"] == updated.id), None)
    if summary_row is None:
        raise HTTPException(status_code=500, detail="Failed to read import summary.")
    return schemas.LibraryImportSummary(**summary_row)


@app.delete(
    "/api/admin/library-imports/{import_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_admin_library_import(
    import_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(security.get_current_active_user),
):
    _require_admin(current_user)
    try:
        deleted = crud.delete_library_import(db, import_id=import_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not deleted:
        raise HTTPException(status_code=404, detail="Library import not found")

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/admin/library-imports/refresh-catalog")
def refresh_admin_library_catalog(
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(security.get_current_active_user),
):
    _require_admin(current_user)
    crud.upsert_app_setting(
        db,
        key=CATALOG_REFRESH_TRIGGERED_AT_SETTING_KEY,
        value=datetime.utcnow().isoformat(),
    )
    return {"message": "Catalog refresh requested."}


@app.get("/api/theme", response_model=schemas.ThemeSettingsResponse)
def get_theme_settings(db: Session = Depends(get_db)):
    primary_color = DEFAULT_THEME_PRIMARY_COLOR
    library_name = None
    setting = crud.get_app_setting(db, THEME_PRIMARY_COLOR_SETTING_KEY)
    if setting and setting.value:
        primary_color = setting.value
    library_name_setting = crud.get_app_setting(db, LIBRARY_NAME_SETTING_KEY)
    if library_name_setting and library_name_setting.value:
        library_name = library_name_setting.value
    collaborative_weight, content_weight, quality_weight = (
        _get_global_recommender_weights(db)
    )
    return schemas.ThemeSettingsResponse(
        primary_color=primary_color,
        library_name=library_name,
        collaborative_weight=collaborative_weight,
        content_weight=content_weight,
        quality_weight=quality_weight,
    )


@app.put("/api/admin/theme", response_model=schemas.ThemeSettingsResponse)
def update_theme_settings(
    request: schemas.ThemeSettingsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(security.get_current_active_user),
):
    _require_admin(current_user)
    if request.primary_color is not None:
        color_setting = crud.upsert_app_setting(
            db,
            key=THEME_PRIMARY_COLOR_SETTING_KEY,
            value=request.primary_color.upper(),
        )
        primary_color = color_setting.value
    else:
        existing_color = crud.get_app_setting(db, THEME_PRIMARY_COLOR_SETTING_KEY)
        primary_color = (
            existing_color.value
            if existing_color and existing_color.value
            else DEFAULT_THEME_PRIMARY_COLOR
        )

    if request.library_name is not None:
        normalized_library_name = request.library_name.strip()
        if normalized_library_name:
            library_name_setting = crud.upsert_app_setting(
                db,
                key=LIBRARY_NAME_SETTING_KEY,
                value=normalized_library_name,
            )
            library_name = library_name_setting.value
        else:
            crud.delete_app_setting(db, LIBRARY_NAME_SETTING_KEY)
            library_name = None
    else:
        existing_library_name = crud.get_app_setting(db, LIBRARY_NAME_SETTING_KEY)
        library_name = (
            existing_library_name.value
            if existing_library_name and existing_library_name.value
            else None
        )

    (
        collaborative_weight,
        content_weight,
        quality_weight,
    ) = _get_global_recommender_weights(db)

    if request.collaborative_weight is not None:
        collaborative_weight_setting = crud.upsert_app_setting(
            db,
            key=RECOMMENDER_COLLABORATIVE_WEIGHT_SETTING_KEY,
            value=str(float(request.collaborative_weight)),
        )
        collaborative_weight = float(collaborative_weight_setting.value)

    if request.content_weight is not None:
        content_weight_setting = crud.upsert_app_setting(
            db,
            key=RECOMMENDER_CONTENT_WEIGHT_SETTING_KEY,
            value=str(float(request.content_weight)),
        )
        content_weight = float(content_weight_setting.value)

    if request.quality_weight is not None:
        quality_weight_setting = crud.upsert_app_setting(
            db,
            key=RECOMMENDER_QUALITY_WEIGHT_SETTING_KEY,
            value=str(float(request.quality_weight)),
        )
        quality_weight = float(quality_weight_setting.value)

    return schemas.ThemeSettingsResponse(
        primary_color=primary_color,
        library_name=library_name,
        collaborative_weight=collaborative_weight,
        content_weight=content_weight,
        quality_weight=quality_weight,
    )


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
    if getattr(current_user, "is_guest", False):
        raise HTTPException(
            status_code=403, detail="Guest sessions cannot change password"
        )
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
    author_user_id = current_user.id
    author_username = current_user.username
    if getattr(current_user, "is_guest", False):
        guest_user = crud.get_or_create_guest_user(db)
        author_user_id = guest_user.id
        author_username = guest_user.username

    logger.info(
        "Creating suggestion for user_id=%s username=%s",
        author_user_id,
        author_username,
    )
    db_suggestion = crud.create_user_suggestion(
        db=db, user_id=author_user_id, suggestion=suggestion
    )
    logger.info(
        "Created suggestion id=%s for user_id=%s",
        db_suggestion.id,
        author_user_id,
    )
    return schemas.UserSuggestionResponse(
        id=db_suggestion.id,
        comment=db_suggestion.comment,
        timestamp=db_suggestion.timestamp.isoformat(),
        username=author_username,
    )


# Serve static frontend files
if os.path.exists(STATIC_DIR):
    logger.info(f"Mounting React frontend from {STATIC_DIR}")
    app.mount(
        "/", SPAStaticFiles(directory=str(STATIC_DIR), html=True), name="frontend"
    )
else:
    logger.warning(f"Frontend build directory not found at {STATIC_DIR}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Create user account.")
    parser.add_argument("--username", required=True, help="Username")
    parser.add_argument("--password", help="Password (discouraged; use prompt/stdin)")
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read password from stdin.",
    )
    parser.add_argument(
        "--admin",
        action="store_true",
        help="Create as admin user (default: regular user)",
    )
    parser.add_argument(
        "--reset-password", action="store_true", help="Reset password for existing user"
    )
    args = parser.parse_args()
    try:
        password_value = resolve_cli_password(
            password_arg=args.password,
            use_stdin=args.password_stdin,
        )
    except ValueError as exc:
        raise SystemExit(str(exc))

    if args.reset_password:
        security.reset_password_cli(args.username, password_value)
    else:
        security.create_user_cli(args.username, password_value, args.admin)
