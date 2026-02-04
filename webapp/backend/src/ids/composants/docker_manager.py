import os
import subprocess
from pathlib import Path

from ..app.decorateurs import log_appel, metriques, retry
from ..domain import ConditionSante
from ..interfaces import GestionnaireConfig
from .base import BaseComponent


class DockerManager(BaseComponent):
    """Manage Docker Compose lifecycle for IDS services."""

    def __init__(self, config: GestionnaireConfig) -> None:
        super().__init__(config, "docker")
        self._compose_file = self._resolve_compose_file()

    def _resolve_compose_file(self) -> Path:
        compose_path = (
            self._config.obtenir("docker.compose_file")
            or self._config.obtenir("docker.compose_path")
            or "docker/docker-compose.yml"
        )
        return Path(compose_path)

    def _run(self, args: list[str]) -> None:
        if os.environ.get("IDS_DRY_RUN") == "1":
            self._logger.info("Dry-run docker: %s", " ".join(args))
            return
        subprocess.run(args, check=True)

    def _compose_command(self, *parts: str) -> list[str]:
        return ["docker", "compose", "-f", str(self._compose_file), *parts]

    @log_appel()
    @metriques("docker.start")
    @retry(nb_tentatives=3, delai_initial=1.0, backoff=2.0)
    async def demarrer(self) -> None:
        self._run(self._compose_command("up", "-d"))
        self._is_running = True

    @log_appel()
    @metriques("docker.stop")
    async def arreter(self) -> None:
        self._run(self._compose_command("down"))
        self._is_running = False

    @log_appel()
    @metriques("docker.health")
    async def verifier_sante(self) -> ConditionSante:
        try:
            self._run(self._compose_command("ps"))
            sain = True
            message = "Docker Compose OK"
        except subprocess.CalledProcessError as exc:
            sain = False
            message = f"Docker Compose erreur: {exc}"
        return ConditionSante(
            nom_composant=self.nom_composant,
            sain=sain,
            message=message,
            details={"compose_file": str(self._compose_file)},
        )


__all__ = ["DockerManager"]
