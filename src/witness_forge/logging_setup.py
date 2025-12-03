from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

DEFAULT_LOG_PATH = Path("logs/witness.log")
DEFAULT_LEVEL = logging.INFO


def setup_logging(log_path: str | Path = DEFAULT_LOG_PATH, level: int = DEFAULT_LEVEL) -> logging.Logger:
    """
    Configure a rotating file logger. Safe to call multiple times.
    """
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("witness_forge")
    logger.setLevel(level)

    if not any(isinstance(h, RotatingFileHandler) and getattr(h, "baseFilename", None) == str(log_path) for h in logger.handlers):
        handler = RotatingFileHandler(str(log_path), maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(logging.Formatter("%(levelname)s | %(message)s"))
        logger.addHandler(console_handler)

    logger.debug("Logging configured at level %s", logging.getLevelName(level))
    return logger


__all__ = ["setup_logging", "DEFAULT_LOG_PATH", "DEFAULT_LEVEL"]
