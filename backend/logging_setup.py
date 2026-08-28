import logging
from logging.handlers import RotatingFileHandler

from backend.config.settings import LOGS_DIR

_configured = False


def setup_logging() -> logging.Logger:
    global _configured
    logger = logging.getLogger("ai_voice_studio")
    if _configured:
        return logger

    logger.setLevel(logging.INFO)

    file_handler = RotatingFileHandler(
        LOGS_DIR / "app.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(console_handler)

    _configured = True
    return logger


logger = setup_logging()
