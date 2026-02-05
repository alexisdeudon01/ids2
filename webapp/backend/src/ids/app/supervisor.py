"""
Agent Supervisor - Point d'entree principal de l'agent IDS.
"""

import asyncio
import logging
import signal
import sys
from enum import Enum
from pathlib import Path

from ..composants import DockerManager, ResourceController
from ..config.loader import ConfigManager
from ..suricata import SuricataManager
from .container import ConteneurFactory
from .decorateurs import log_appel, metriques, retry
from .pipeline_status import PipelineStatusAggregator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class SupervisorState(Enum):
    WAIT_USER = "WaitUser"
    START_COMMAND = "StartCommand"
    INITIALIZING = "Initializing"
    COMPONENTS_STARTING = "ComponentsStarting"
    SUPERVISOR_RUNNING = "SupervisorRunning"
    STOPPING = "Stopping"
    STOPPED = "Stopped"


class InitializingSubState(Enum):
    LOADING_CONFIG = "LoadingConfig"
    VALIDATING_CONFIG = "ValidatingConfig"
    CONFIG_VALID = "ConfigValid"
    CONFIG_ERROR = "ConfigError"


class ComponentsSubState(Enum):
    START_RESOURCE_CONTROLLER = "StartResourceController"
    START_DOCKER_MANAGER = "StartDockerManager"
    START_SURICATA_MANAGER = "StartSuricataManager"
    ALL_COMPONENTS_STARTED = "AllComponentsStarted"


class SupervisorRunningSubState(Enum):
    SUPERVISOR_MONITORING = "SupervisorMonitoring"
    HEALTH_OK = "HealthOK"
    SUPERVISOR_DEGRADED = "SupervisorDegraded"
    SUPERVISOR_RECOVERING = "SupervisorRecovering"


class StoppingSubState(Enum):
    STOP_SURICATA = "StopSuricata"
    STOP_DOCKER = "StopDocker"
    STOP_RESOURCE_CONTROLLER = "StopResourceController"
    ALL_STOPPED = "AllStopped"


class AgentSupervisor:
    """Superviseur principal de l'agent IDS."""

    def __init__(self, config_path: str = "config.yaml") -> None:
        self.config_path = Path(config_path)
        self.config_manager = ConfigManager(str(self.config_path))
        self.container = ConteneurFactory.creer_conteneur_prod(str(self.config_path))
        self._shutdown_event = asyncio.Event()
        self._tasks: list[asyncio.Task] = []
        self._resource_controller: ResourceController | None = None
        self._docker_manager: DockerManager | None = None
        self._suricata_manager: SuricataManager | None = None
        self._monitor_task: asyncio.Task | None = None
        self._monitor_interval = 5.0
        self._recovery_attempts = 0
        self._max_recovery_attempts = 2

        self._state = SupervisorState.WAIT_USER
        self._init_substate: InitializingSubState | None = None
        self._components_substate: ComponentsSubState | None = None
        self._supervisor_substate: SupervisorRunningSubState | None = None
        self._stopping_substate: StoppingSubState | None = None

    def _set_state(self, state: SupervisorState) -> None:
        if self._state != state:
            logger.info("FSM: %s -> %s", self._state.value, state.value)
            self._state = state

    def _set_init_substate(self, state: InitializingSubState) -> None:
        self._init_substate = state
        logger.info("FSM: Initializing::%s", state.value)

    def _set_components_substate(self, state: ComponentsSubState) -> None:
        self._components_substate = state
        logger.info("FSM: ComponentsStarting::%s", state.value)

    def _set_supervisor_substate(self, state: SupervisorRunningSubState) -> None:
        self._supervisor_substate = state
        logger.info("FSM: SupervisorRunning::%s", state.value)

    def _set_stopping_substate(self, state: StoppingSubState) -> None:
        self._stopping_substate = state
        logger.info("FSM: Stopping::%s", state.value)

    def _validate_config(self) -> bool:
        required_keys = [
            "suricata.config_path",
            "vector.config_path",
            "raspberry_pi.network_interface",
        ]
        for key in required_keys:
            if not self.config_manager.obtenir(key):
                logger.error("Configuration manquante: %s", key)
                return False
        return True

    async def _monitor_loop(self) -> None:
        while not self._shutdown_event.is_set():
            self._set_supervisor_substate(SupervisorRunningSubState.SUPERVISOR_MONITORING)
            health_ok = await self._check_health()
            if health_ok:
                self._set_supervisor_substate(SupervisorRunningSubState.HEALTH_OK)
                self._recovery_attempts = 0
            else:
                self._set_supervisor_substate(SupervisorRunningSubState.SUPERVISOR_DEGRADED)
                recovered = await self._attempt_recovery()
                if not recovered:
                    self._set_supervisor_substate(SupervisorRunningSubState.SUPERVISOR_RECOVERING)
                    logger.error("Recuperation impossible. Arret du superviseur.")
                    self._set_state(SupervisorState.STOPPED)
                    self._shutdown_event.set()
                    return
                self._set_supervisor_substate(SupervisorRunningSubState.SUPERVISOR_RECOVERING)
            await asyncio.sleep(self._monitor_interval)

    async def _check_health(self) -> bool:
        try:
            if self._resource_controller is not None:
                if not (await self._resource_controller.verifier_sante()).sain:
                    return False
            if self._docker_manager is not None:
                if not (await self._docker_manager.verifier_sante()).sain:
                    return False
            if self._suricata_manager is not None:
                if not (await self._suricata_manager.verifier_sante()).sain:
                    return False
        except Exception as exc:
            logger.error("Erreur verification sante: %s", exc, exc_info=True)
            return False
        return True

    async def _attempt_recovery(self) -> bool:
        if self._recovery_attempts >= self._max_recovery_attempts:
            return False
        self._recovery_attempts += 1
        self._set_supervisor_substate(SupervisorRunningSubState.SUPERVISOR_RECOVERING)

        ok = True
        for manager in (self._resource_controller, self._docker_manager, self._suricata_manager):
            if manager is None:
                continue
            if hasattr(manager, "marquer_recuperation"):
                manager.marquer_recuperation(None)
            try:
                if not (await manager.verifier_sante()).sain:
                    await manager.demarrer()
            except Exception as exc:
                logger.error("Erreur de recuperation: %s", exc, exc_info=True)
                ok = False
        for manager in (self._resource_controller, self._docker_manager, self._suricata_manager):
            if manager is None:
                continue
            if hasattr(manager, "marquer_recuperation"):
                manager.marquer_recuperation(ok)
        return ok

    @log_appel()
    @metriques("agent_start")
    @retry(nb_tentatives=2, delai_initial=0.5, backoff=2.0)
    async def demarrer(self) -> None:
        logger.info("Demarrage de l'agent IDS2 SOC...")

        self._set_state(SupervisorState.START_COMMAND)
        self._set_state(SupervisorState.INITIALIZING)

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._signal_handler, sig)

        try:
            self._set_init_substate(InitializingSubState.LOADING_CONFIG)
            try:
                self.config_manager.recharger()
            except Exception as exc:
                self._set_init_substate(InitializingSubState.CONFIG_ERROR)
                self._set_state(SupervisorState.STOPPED)
                logger.error("Erreur chargement config: %s", exc, exc_info=True)
                raise

            self._set_init_substate(InitializingSubState.VALIDATING_CONFIG)
            if not self._validate_config():
                self._set_init_substate(InitializingSubState.CONFIG_ERROR)
                self._set_state(SupervisorState.STOPPED)
                raise RuntimeError("Validation de configuration echouee.")
            self._set_init_substate(InitializingSubState.CONFIG_VALID)

            self._set_state(SupervisorState.COMPONENTS_STARTING)
            self._set_components_substate(ComponentsSubState.START_RESOURCE_CONTROLLER)
            self._resource_controller = self.container.resoudre(ResourceController)
            await self._resource_controller.demarrer()

            self._set_components_substate(ComponentsSubState.START_DOCKER_MANAGER)
            self._docker_manager = self.container.resoudre(DockerManager)
            await self._docker_manager.demarrer()

            self._set_components_substate(ComponentsSubState.START_SURICATA_MANAGER)
            self._suricata_manager = self.container.resoudre(SuricataManager)
            await self._suricata_manager.demarrer()
            self._set_components_substate(ComponentsSubState.ALL_COMPONENTS_STARTED)

            self._set_state(SupervisorState.SUPERVISOR_RUNNING)
            self._set_supervisor_substate(SupervisorRunningSubState.SUPERVISOR_MONITORING)

            self.container.resoudre(PipelineStatusAggregator)
            self._monitor_task = asyncio.create_task(self._monitor_loop())
            self._tasks.append(self._monitor_task)

            logger.info("Agent IDS2 SOC demarre avec succes")
            await self._shutdown_event.wait()
        except Exception as exc:
            if self._state in (
                SupervisorState.INITIALIZING,
                SupervisorState.COMPONENTS_STARTING,
                SupervisorState.START_COMMAND,
            ):
                self._set_state(SupervisorState.STOPPED)
            logger.error("Erreur lors du demarrage de l'agent: %s", exc, exc_info=True)
            raise
        finally:
            await self.arreter()

    @log_appel()
    @metriques("agent_stop")
    @retry(nb_tentatives=2, delai_initial=0.5, backoff=2.0)
    async def arreter(self) -> None:
        logger.info("Arret de l'agent IDS2 SOC...")

        if self._state == SupervisorState.STOPPED:
            return
        if self._state == SupervisorState.SUPERVISOR_RUNNING:
            self._set_state(SupervisorState.STOPPING)

        for task in self._tasks:
            if not task.done():
                task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        self._set_stopping_substate(StoppingSubState.STOP_SURICATA)
        if self._suricata_manager is not None:
            await self._suricata_manager.arreter()
        self._set_stopping_substate(StoppingSubState.STOP_DOCKER)
        if self._docker_manager is not None:
            await self._docker_manager.arreter()
        self._set_stopping_substate(StoppingSubState.STOP_RESOURCE_CONTROLLER)
        if self._resource_controller is not None:
            await self._resource_controller.arreter()
        self._set_stopping_substate(StoppingSubState.ALL_STOPPED)
        self._set_state(SupervisorState.STOPPED)

        logger.info("Agent IDS2 SOC arrete")

    def _signal_handler(self, sig: signal.Signals) -> None:
        logger.info("Signal %s recu, arret en cours...", sig.name)
        self._shutdown_event.set()


def main() -> int:
    try:
        config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
        supervisor = AgentSupervisor(config_path)
        asyncio.run(supervisor.demarrer())
        return 0
    except KeyboardInterrupt:
        logger.info("Interruption clavier, arret...")
        return 0
    except Exception as exc:
        logger.error("Erreur fatale: %s", exc, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
