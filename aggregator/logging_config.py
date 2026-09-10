"""
aggregator/logging_config.py - Structured logging setup.

Uses stdlib logging (simple, no structlog dep issues).
All modules call get_logger(__name__).
"""

import logging
import sys

from aggregator import config


def setup_logging(level: str | None = None, log_file: str | None = None) -> None:
    """Configure root logger with console (and optional file) handler."""
    lvl = getattr(logging, (level or config.LOG_LEVEL).upper(), logging.INFO)
    fmt = "%(asctime)s %(levelname)-8s %(name)s - %(message)s"
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file or config.LOG_FILE:
        from logging.handlers import RotatingFileHandler
        fh = RotatingFileHandler(log_file or config.LOG_FILE, maxBytes=5_000_000, backupCount=3)
        fh.setFormatter(logging.Formatter(fmt))
        handlers.append(fh)
    logging.basicConfig(level=lvl, format=fmt, handlers=handlers, force=True)


def get_logger(name: str) -> logging.Logger:
    """Return a logger for the given module name."""
    return logging.getLogger(name)
