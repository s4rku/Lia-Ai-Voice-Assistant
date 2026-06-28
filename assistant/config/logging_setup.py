"""
Structured, colourised logging for lia.
Uses loguru – single call to `setup_logging()` from main.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from .settings import LOG_DIR, settings


def setup_logging() -> None:
    """Configure loguru sinks: stderr (colourised) + rotating file."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "lia.log"

    # Remove the default sink so we control formatting completely.
    logger.remove()

    # ── Console ──────────────────────────────────────────────────────────────
    fmt_console = (
        "<green>{time:HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    logger.add(
        sys.stderr,
        format=fmt_console,
        level=settings.log_level,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    # ── Rotating file ────────────────────────────────────────────────────────
    fmt_file = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
        "{level: <8} | "
        "{name}:{function}:{line} | "
        "{message}"
    )
    logger.add(
        log_file,
        format=fmt_file,
        level="DEBUG",          # always debug-level to file
        rotation=settings.log_rotation,
        retention=settings.log_retention,
        compression="zip",
        encoding="utf-8",
        backtrace=True,
        diagnose=True,
    )

    logger.info("Logging initialised — level={} file={}", settings.log_level, log_file)


# ── Convenience helpers ──────────────────────────────────────────────────────
def get_logger(name: str):  # noqa: ANN201
    """Return a named child logger (bind name to every record)."""
    return logger.bind(name=name)
