import sys
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from alembic.config import Config  # noqa: E402
from alembic import command  # noqa: E402


def setup_database():
    """Set up the database for production."""
    # Use Alembic as the single schema authority.
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")


if __name__ == "__main__":
    setup_database()
