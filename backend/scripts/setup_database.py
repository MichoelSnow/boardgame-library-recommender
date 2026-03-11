import sys
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.database import engine  # noqa: E402
from app.models import Base  # noqa: E402
from alembic.config import Config  # noqa: E402
import alembic.command as alembic_command  # noqa: E402


def setup_database():
    """Set up the database for production."""
    # Create tables
    Base.metadata.create_all(bind=engine)

    # Run migrations
    alembic_cfg = Config("alembic.ini")
    alembic_command.upgrade(alembic_cfg, "head")


if __name__ == "__main__":
    setup_database()
