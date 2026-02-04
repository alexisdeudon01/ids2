"""
Agent Supervisor - Point d'entree principal de l'agent IDS.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

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


class AgentSupervisor:
    """Superviseur principal de l'agent IDS."""

    def __init__(self, config_path: str = "config.yaml") -> None:
        self.config_path = Path(config_path)
        self.config_manager = ConfigManager(str(self.config_path))
        self.container = ConteneurFactory.creer_conteneur_prod(str(self.config_path))
        self._shutdown_event = asyncio.Event()
        self._tasks: list[asyncio.Task] = []
        self._resource_controller: Optional[ResourceController] = None
        self._docker_manager: Optional[DockerManager] = None
        self._suricata_manager: Optional[SuricataManager] = None

    @log_appel()
    @metriques("agent_start")
    @retry(nb_tentatives=2, delai_initial=0.5, backoff=2.0)
    async def demarrer(self) -> None:
        logger.info("Demarrage de l'agent IDS2 SOC...")

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._signal_handler, sig)

        try:
            self._resource_controller = self.container.resoudre(ResourceController)
            self._docker_manager = self.container.resoudre(DockerManager)
            self._suricata_manager = self.container.resoudre(SuricataManager)

            await self._resource_controller.demarrer()
            await self._docker_manager.demarrer()
            await self._suricata_manager.demarrer()

            self.container.resoudre(PipelineStatusAggregator)

            logger.info("Agent IDS2 SOC demarre avec succes")
            await self._shutdown_event.wait()
        except Exception as exc:
            logger.error("Erreur lors du demarrage de l'agent: %s", exc, exc_info=True)
            raise
        finally:
            await self.arreter()

    @log_appel()
    @metriques("agent_stop")
    @retry(nb_tentatives=2, delai_initial=0.5, backoff=2.0)
    async def arreter(self) -> None:
        logger.info("Arret de l'agent IDS2 SOC...")

        for task in self._tasks:
            if not task.done():
                task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        if self._suricata_manager is not None:
            await self._suricata_manager.arreter()
        if self._docker_manager is not None:
            await self._docker_manager.arreter()
        if self._resource_controller is not None:
            await self._resource_controller.arreter()

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
