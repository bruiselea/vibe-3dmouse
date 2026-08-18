"""Release application logging."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_release_logging(path: Path) -> logging.Logger:
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("spacemouse_codex")
    logger.setLevel(logging.DEBUG)
    if not any(
        isinstance(handler, RotatingFileHandler)
        and Path(handler.baseFilename) == path.resolve()
        for handler in logger.handlers
    ):
        handler = RotatingFileHandler(
            path,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(threadName)s %(message)s")
        )
        logger.addHandler(handler)
    return logger

