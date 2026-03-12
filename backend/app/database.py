import logging

from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from starlette.responses import Response

from backend.app.db_config import get_database_url, get_engine_kwargs

logger = logging.getLogger(__name__)

SQLALCHEMY_DATABASE_URL = get_database_url()

# Create engine with optimized settings
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    **get_engine_kwargs(SQLALCHEMY_DATABASE_URL),
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Base class for models
class Base(DeclarativeBase):
    pass


# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class CORSAwareStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        response: Response = await super().get_response(path, scope)
        response.headers["Access-Control-Allow-Origin"] = "*"
        # Optionally, add other headers as needed
        return response
