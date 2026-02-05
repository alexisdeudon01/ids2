"""Base class for managed components."""

import asyncio
import logging
from enum import Enum

from ..app.decorateurs import log_appel, metriques, retry
from ..domain import ConditionSante
from ..interfaces import GestionnaireConfig, PipelineStatusProvider


class ComponentState(Enum):
    COMP_STOPPED = "CompStopped"
    COMP_STARTING = "CompStarting"
    COMP_RUNNING = "CompRunning"
    COMP_MONITORING = "CompMonitoring"
    COMP_HEALTHY = "CompHealthy"
    COMP_UNHEALTHY = "CompUnhealthy"
    COMP_RECOVERING = "CompRecovering"
    COMP_DEGRADED = "CompDegraded"
    COMP_ERROR = "CompError"
    COMP_STOPPING = "CompStopping"


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
        self._state = ComponentState.COMP_STOPPED

    def _set_state(self, state: ComponentState) -> None:
        if self._state != state:
            self._logger.info("FSM: %s -> %s", self._state.value, state.value)
            self._state = state

    @log_appel()
    @metriques("component.start")
    @retry(nb_tentatives=3, delai_initial=1.0, backoff=2.0)
    async def demarrer(self) -> None:
        self._set_state(ComponentState.COMP_STARTING)
        try:
            self._is_running = True
            self._set_state(ComponentState.COMP_RUNNING)
            self._logger.info("Composant demarre: %s", self.nom_composant)
        except Exception as exc:
            self._set_state(ComponentState.COMP_ERROR)
            self._logger.error("Erreur demarrage composant: %s", exc, exc_info=True)
            raise

    @log_appel()
    @metriques("component.stop")
    async def arreter(self) -> None:
        self._set_state(ComponentState.COMP_STOPPING)
        self._shutdown_event.set()
        self._is_running = False
        self._set_state(ComponentState.COMP_STOPPED)
        self._logger.info("Composant arrete: %s", self.nom_composant)

    @log_appel()
    @metriques("component.health")
    async def verifier_sante(self) -> ConditionSante:
        self._set_state(ComponentState.COMP_MONITORING)
        try:
            if self._is_running:
                self._set_state(ComponentState.COMP_HEALTHY)
            else:
                self._set_state(ComponentState.COMP_UNHEALTHY)
            return ConditionSante(
                nom_composant=self.nom_composant,
                sain=self._is_running,
                message="Operationnel" if self._is_running else "Arrete",
                details={"running": self._is_running},
            )
        except Exception as exc:
            self._set_state(ComponentState.COMP_ERROR)
            self._logger.error("Erreur verification sante: %s", exc, exc_info=True)
            return ConditionSante(
                nom_composant=self.nom_composant,
                sain=False,
                message="Erreur verification sante",
                details={"error": str(exc)},
            )

    async def fournir_statut(self) -> ConditionSante:
        return await self.verifier_sante()

    @log_appel()
    async def recharger_config(self) -> None:
        if self._config is None:
            return
        self._config.recharger()
        self._logger.info("Configuration rechargee: %s", self.nom_composant)

    def marquer_recuperation(self, succes: bool | None = None) -> None:
        previous_state = self._state
        self._set_state(ComponentState.COMP_RECOVERING)
        if succes is True:
            self._set_state(ComponentState.COMP_HEALTHY)
        elif succes is False:
            if previous_state == ComponentState.COMP_DEGRADED:
                self._set_state(ComponentState.COMP_ERROR)
            else:
                self._set_state(ComponentState.COMP_DEGRADED)
        else:
            self._set_state(ComponentState.COMP_DEGRADED)

    def shutdown_requested(self) -> bool:
        return self._shutdown_event.is_set()

    @property
    def is_running(self) -> bool:
        return self._is_running


__all__ = ["BaseComponent", "ComponentState"]
