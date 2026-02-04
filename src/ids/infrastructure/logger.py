"""
Logging utilities for the IDS agent.
"""

from __future__ import annotations

import logging
from typing import Optional

try:
    from pythonjsonlogger import jsonlogger
except ImportError:  # pragma: no cover - optional
    jsonlogger = None

from ..interfaces import LoggerIDS


class LoggerStandard(LoggerIDS):
    """Implementation simple basee sur logging."""

    def __init__(self, nom: Optional[str] = None) -> None:
        self._logger = logging.getLogger(nom or __name__)

    def info(self, message: str) -> None:
        self._logger.info(message)

    def erreur(self, message: str, exception: Optional[Exception] = None) -> None:
        self._logger.error(message, exc_info=exception is not None)

    def debug(self, message: str) -> None:
        self._logger.debug(message)


def configurer_logging(niveau: str = "INFO") -> None:
    """Configure un logging standard ou JSON selon la disponibilite."""
    level = getattr(logging, niveau.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler()
    if jsonlogger:
        formatter = jsonlogger.JsonFormatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    else:
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)

    root.handlers.clear()
    root.addHandler(handler)


__all__ = ["LoggerStandard", "configurer_logging"]
