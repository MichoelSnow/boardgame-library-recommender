import logging
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOGS_DIR = PROJECT_ROOT / "logs"


def get_logs_dir() -> Path:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return LOGS_DIR


def build_log_handlers(filename: str) -> list[logging.Handler]:
    log_path = get_logs_dir() / filename
    return [
        logging.FileHandler(str(log_path)),
        logging.StreamHandler(),
    ]
