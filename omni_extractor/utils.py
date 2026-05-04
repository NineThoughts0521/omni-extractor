"""Utility functions for omni-extractor."""

import sys

from loguru import logger


def setup_logging(log_level: str = "INFO", sink: str | None = None) -> None:
    """Configure loguru logging for the application.

    Removes the default handler and adds a new stderr (or file) handler with
    the requested log level.  This keeps library noise low while still
    surfacing omni-extractor messages.

    Args:
        log_level: Minimum severity to emit (DEBUG, INFO, WARNING, ERROR,
            CRITICAL).  Defaults to ``INFO``.
        sink: Optional file path to write logs to.  If ``None``, logs are
            written to ``stderr``.
    """
    logger.remove()
    logger.add(
        sink or sys.stderr,
        level=log_level.upper(),
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True if sink is None else False,
    )


__all__ = ["setup_logging"]
