"""
Elasticsearch cluster health monitoring.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from typing import Any

from elasticsearch import AsyncElasticsearch

from ids.domain import ElasticsearchHealth

logger = logging.getLogger(__name__)

DSL_AVAILABLE = False
Index: type | None = None
connections: Any | None = None
try:
    from elasticsearch_dsl import Index  # type: ignore[assignment,no-redef]
    from elasticsearch_dsl.connections import connections  # type: ignore[assignment,no-redef]

    DSL_AVAILABLE = True
except ImportError:
    logger.warning("elasticsearch-dsl not available. Install with: pip install elasticsearch-dsl")


class ElasticsearchMonitor:
    """Monitor Elasticsearch cluster health and indices."""

    def __init__(
        self,
        hosts: list[str] | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        """
        Initialize Elasticsearch monitor.

        Args:
            hosts: List of Elasticsearch host URLs (default: ["http://localhost:9200"])
            username: Optional username for authentication
            password: Optional password for authentication
        """
        self.hosts = hosts or ["http://localhost:9200"]
        self.username = username
        self.password = password
        self._client: AsyncElasticsearch | None = None

    async def connect(self) -> None:
        """Establish connection to Elasticsearch."""
        try:
            auth = None
            if self.username and self.password:
                auth = (self.username, self.password)

            self._client = AsyncElasticsearch(
                hosts=self.hosts,
                basic_auth=auth,
                request_timeout=10,
            )

            if DSL_AVAILABLE and connections is not None:
                connections.add_connection("default", self._client)  # type: ignore[unreachable]

            # Test connection
            info = await self._client.info()
            logger.info(f"Connected to Elasticsearch: {info.get('cluster_name', 'unknown')}")

        except Exception as e:
            logger.error(f"Failed to connect to Elasticsearch: {e}")
            self._client = None

    async def disconnect(self) -> None:
        """Close Elasticsearch connection."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Disconnected from Elasticsearch")

    async def get_cluster_health(self) -> ElasticsearchHealth | None:
        """
        Get Elasticsearch cluster health status.

        Returns:
            ElasticsearchHealth object or None if unavailable
        """
        if not self._client:
            await self.connect()

        if not self._client:
            return None

        try:
            health_response = await self._client.cluster.health()
            indices_response = await self._client.cat.indices(
                format="json",
                h="index,creation.date",
            )

            # Count daily indices (indices created today)
            today = datetime.now().date()
            daily_count = await self._count_daily_indices(today, indices_response)

            return ElasticsearchHealth(
                status=health_response.get("status", "unknown"),
                cluster_name=health_response.get("cluster_name", "unknown"),
                number_of_nodes=health_response.get("number_of_nodes", 0),
                number_of_data_nodes=health_response.get("number_of_data_nodes", 0),
                active_primary_shards=health_response.get("active_primary_shards", 0),
                active_shards=health_response.get("active_shards", 0),
                relocating_shards=health_response.get("relocating_shards", 0),
                initializing_shards=health_response.get("initializing_shards", 0),
                unassigned_shards=health_response.get("unassigned_shards", 0),
                daily_indices_count=daily_count,
            )

        except Exception as e:
            logger.error(f"Error getting cluster health: {e}")
            return None

    async def _count_daily_indices(
        self,
        today: date,
        indices_response: list[dict[str, Any]],
    ) -> int:
        if DSL_AVAILABLE and Index is not None:
            try:
                index_settings = await asyncio.to_thread(Index("*").get_settings)
                count = 0
                for index_name, settings in index_settings.items():
                    creation_ms = (
                        settings.get("settings", {})
                        .get("index", {})
                        .get("creation_date")
                    )
                    if creation_ms:
                        creation_date = datetime.fromtimestamp(int(creation_ms) / 1000.0).date()
                        if creation_date == today:
                            count += 1
                            continue
                    if self._index_name_matches_date(index_name, today):
                        count += 1
                return count
            except Exception as exc:
                logger.debug(f"DSL index count failed, falling back: {exc}")

        count = 0
        for idx in indices_response:
            index_name = idx.get("index", "")
            if self._index_name_matches_date(index_name, today):
                count += 1
        return count

    @staticmethod
    def _index_name_matches_date(index_name: str, today: date) -> bool:
        if "." not in index_name:
            return False
        try:
            parts = index_name.split(".")
            if len(parts) >= 3:
                year = int(parts[-3])
                month = int(parts[-2])
                day = int(parts[-1])
                return datetime(year, month, day).date() == today
        except (ValueError, IndexError):
            return False
        return False

    async def get_index_stats(self, index_pattern: str = "logstash-*") -> dict[str, Any]:
        """
        Get statistics for indices matching a pattern.

        Args:
            index_pattern: Index pattern (e.g., "logstash-*")

        Returns:
            Dictionary with index statistics
        """
        if not self._client:
            await self.connect()

        if not self._client:
            return {}

        try:
            stats = await self._client.indices.stats(index=index_pattern)
            return stats

        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            return {}
