import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

from app.core.config import settings, ROOT_DIR


def setup_logging():
    log_path = ROOT_DIR / settings.LOG_FILE
    log_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper()),
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(name)s | "
            "%(message)s"
        ),
        handlers=[
            RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8"),
            logging.StreamHandler(),
        ],
        force=True,
    )
