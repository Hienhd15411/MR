from __future__ import annotations

import sys
from datetime import datetime
from loguru import logger

from src.config.settings import LOG_DIR, LOG_LEVEL

_configured = False


def setup_logger() -> None:
    global _configured
    if _configured:
        return
    logger.remove()
    logger.add(sys.stderr, level=LOG_LEVEL, enqueue=False)
    log_file = LOG_DIR / f"run-{datetime.utcnow().strftime('%Y%m%d')}.log"
    logger.add(log_file, level="DEBUG", rotation="10 MB", retention="30 days", enqueue=False)
    _configured = True
