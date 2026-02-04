"""
Client Redis minimal.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import redis

from ..app.decorateurs import log_appel, metriques, retry

if TYPE_CHECKING:
    from ..interfaces import GestionnaireConfig

logger = logging.getLogger(__name__)


class RedisClient:
    """Client Redis avec ping simple."""

    def __init__(self, config: GestionnaireConfig | None = None) -> None:
        host = "localhost"
        port = 6379
        db = 0
        if config:
            host = config.obtenir("redis.host", host)
            port = config.obtenir("redis.port", port)
            db = config.obtenir("redis.db", db)
        self._client = redis.Redis(host=host, port=port, db=db)

    @log_appel()
    @metriques("redis.ping")
    @retry(nb_tentatives=2, delai_initial=0.5)
    async def ping(self) -> bool:
        def _call() -> bool:
            try:
                return bool(self._client.ping())
            except redis.RedisError as exc:
                logger.warning("Ping Redis echoue: %s", exc)
                return False

        return await asyncio.to_thread(_call)

    def close(self) -> None:
        self._client.close()


__all__ = ["RedisClient"]
