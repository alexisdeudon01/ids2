"""Base class for managed components."""

import asyncio
import logging

from ..app.decorateurs import log_appel, metriques, retry
from ..domain import ConditionSante
from ..interfaces import GestionnaireConfig, PipelineStatusProvider


class BaseComponent(PipelineStatusProvider):
    """Base class for managed components."""

    def __init__(self, arg1, arg2: GestionnaireConfig | None = None) -> None:
        # Support both (config, name) and (name, config) for backward compatibility.
        if isinstance(arg1, str):
            nom_composant = arg1
            config = arg2
        else:
            config = arg1
            nom_composant = arg2 or self.__class__.__name__.lower()

        self._config: GestionnaireConfig | None = config
        self.nom_composant = nom_composant
        self.nom = nom_composant
        self._shutdown_event = asyncio.Event()
        self._is_running = False
        self._logger = logging.getLogger(f"{__name__}.{nom_composant}")

    @log_appel()
    @metriques("component.start")
    @retry(nb_tentatives=3, delai_initial=1.0, backoff=2.0)
    async def demarrer(self) -> None:
        self._is_running = True
        self._logger.info("Composant demarre: %s", self.nom_composant)

    @log_appel()
    @metriques("component.stop")
    async def arreter(self) -> None:
        self._shutdown_event.set()
        self._is_running = False
        self._logger.info("Composant arrete: %s", self.nom_composant)

    @log_appel()
    @metriques("component.health")
    async def verifier_sante(self) -> ConditionSante:
        return ConditionSante(
            nom_composant=self.nom_composant,
            sain=self._is_running,
            message="Operationnel" if self._is_running else "Arrete",
            details={"running": self._is_running},
        )

    async def fournir_statut(self) -> ConditionSante:
        return await self.verifier_sante()

    @log_appel()
    async def recharger_config(self) -> None:
        if self._config is None:
            return
        self._config.recharger()
        self._logger.info("Configuration rechargee: %s", self.nom_composant)

    def shutdown_requested(self) -> bool:
        return self._shutdown_event.is_set()

    @property
    def is_running(self) -> bool:
        return self._is_running


__all__ = ["BaseComponent"]
