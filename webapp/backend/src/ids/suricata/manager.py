import asyncio
import os
from collections.abc import AsyncGenerator
from pathlib import Path

from ..app.decorateurs import log_appel, metriques, retry
from ..composants.base import BaseComponent
from ..domain import AlerteIDS, ConditionSante
from ..interfaces import AlerteSource, GestionnaireConfig
from .parser import parse_eve_json_line


class SuricataManager(BaseComponent, AlerteSource):
    """Suricata alert source manager (reads eve.json)."""

    def __init__(self, config: GestionnaireConfig) -> None:
        super().__init__(config, "suricata")
        log_path = self._config.obtenir("suricata.log_path", "/mnt/ram_logs/eve.json")
        self._log_path = Path(log_path)

    @log_appel()
    @metriques("suricata.alerts")
    async def fournir_alertes(self) -> AsyncGenerator[AlerteIDS, None]:
        handle = await self._ouvrir_fichier()
        if handle is None:
            while not self.shutdown_requested():
                await asyncio.sleep(1.0)
            return

        with handle:
            while not self.shutdown_requested():
                line = handle.readline()
                if not line:
                    await asyncio.sleep(0.2)
                    continue
                alerte = parse_eve_json_line(line)
                if alerte:
                    yield alerte

    async def _ouvrir_fichier(self) -> object | None:
        if not self._log_path.exists():
            self._logger.warning("Fichier eve.json introuvable: %s", self._log_path)
            return None
        handle = open(self._log_path, encoding="utf-8")
        handle.seek(0, os.SEEK_END)
        return handle

    @log_appel()
    @retry(nb_tentatives=3, delai_initial=1.0, backoff=2.0)
    async def valider_connexion(self) -> bool:
        return self._log_path.exists()

    @log_appel()
    @metriques("suricata.health")
    async def verifier_sante(self) -> ConditionSante:
        exists = self._log_path.exists()
        return ConditionSante(
            nom_composant=self.nom_composant,
            sain=exists,
            message="eve.json present" if exists else "eve.json absent",
            details={"log_path": str(self._log_path)},
        )


__all__ = ["SuricataManager"]
