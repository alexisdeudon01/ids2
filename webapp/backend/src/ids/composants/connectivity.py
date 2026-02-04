import subprocess

import aiohttp

from ..app.decorateurs import log_appel, metriques, retry
from ..domain import ConditionSante
from ..interfaces import GestionnaireConfig
from .base import BaseComponent


class ConnectivityTester(BaseComponent):
    """Connectivity checks for critical dependencies."""

    def __init__(self, config: GestionnaireConfig) -> None:
        super().__init__(config, "connectivity")

    def _get_opensearch_endpoint(self) -> str | None:
        endpoint = self._config.obtenir("aws.opensearch_endpoint")
        if endpoint:
            return endpoint
        return self._config.obtenir("aws.opensearch.endpoint")

    @log_appel()
    @metriques("connectivity.opensearch")
    @retry(nb_tentatives=3, delai_initial=1.0, backoff=2.0)
    async def verifier_opensearch(self) -> ConditionSante:
        endpoint = self._get_opensearch_endpoint()
        if not endpoint:
            return ConditionSante(
                nom_composant="opensearch",
                sain=False,
                message="Endpoint OpenSearch manquant",
            )

        try:
            async with aiohttp.ClientSession() as session, session.get(endpoint, timeout=5) as response:
                sain = response.status < 500
                message = f"HTTP {response.status}"
        except Exception as exc:
            sain = False
            message = f"Erreur: {exc}"

        return ConditionSante(
            nom_composant="opensearch",
            sain=sain,
            message=message,
            details={"endpoint": endpoint},
        )

    @log_appel()
    @metriques("connectivity.docker")
    async def verifier_docker(self) -> ConditionSante:
        try:
            subprocess.run(["docker", "--version"], check=True, capture_output=True)
            sain = True
            message = "Docker OK"
        except subprocess.CalledProcessError as exc:
            sain = False
            message = f"Erreur docker: {exc}"
        return ConditionSante(
            nom_composant="docker",
            sain=sain,
            message=message,
        )


ConnectivityChecker = ConnectivityTester

__all__ = ["ConnectivityChecker", "ConnectivityTester"]
