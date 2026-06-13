"""Structured logging configuration using stdlib logging + rich handler."""

import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    try:
        from rich.logging import RichHandler
        handler: logging.Handler = RichHandler(rich_tracebacks=True)
    except ImportError:
        handler = logging.StreamHandler(sys.stderr)

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[handler],
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
