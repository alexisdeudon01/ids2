"""
MetricsCollector - collecte de metriques systeme (placeholder).
"""

from __future__ import annotations

import logging
import time

from ..app.decorateurs import log_appel, metriques
from ..domain import MetriquesSystem
from ..interfaces import GestionnaireConfig, MetriquesProvider
from .base import BaseComponent

logger = logging.getLogger(__name__)


class MetricsCollector(BaseComponent, MetriquesProvider):
    """Collecte des metriques systeme minimales."""

    def __init__(self, config: GestionnaireConfig | None = None) -> None:
        super().__init__(config, "metrics_collector")
        self._start_time = time.monotonic()

    @log_appel()
    @metriques("metrics.collect")
    async def collecter_metriques(self) -> MetriquesSystem:
        uptime = int(time.monotonic() - self._start_time)
        return MetriquesSystem(uptime_secondes=uptime)

    @log_appel()
    async def enregistrer(self, nom: str, valeur: float) -> None:
        logger.debug("Metrique %s=%s", nom, valeur)


MetricsServer = MetricsCollector

__all__ = ["MetricsCollector", "MetricsServer"]
