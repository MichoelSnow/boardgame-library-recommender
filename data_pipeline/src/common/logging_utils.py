import logging
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOGS_DIR = PROJECT_ROOT / "logs"


def get_logs_dir() -> Path:
    # Prefer explicit override for environments that need persistent mounted logs
    # (e.g., Fly ingest worker writing to /app/data).
    override = os.getenv("DATA_PIPELINE_LOG_DIR", "").strip()
    logs_dir = Path(override) if override else LOGS_DIR
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def build_log_handlers(filename: str) -> list[logging.Handler]:
    log_path = get_logs_dir() / filename
    return [
        logging.FileHandler(str(log_path)),
        logging.StreamHandler(),
    ]
