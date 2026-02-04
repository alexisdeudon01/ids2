import os

from ..app.decorateurs import log_appel, metriques, retry
from ..domain import ConditionSante, MetriquesSystem
from ..interfaces import GestionnaireConfig, MetriquesProvider
from .base import BaseComponent


class ResourceController(BaseComponent, MetriquesProvider):
    """Simple resource controller with placeholder metrics."""

    def __init__(self, config: GestionnaireConfig) -> None:
        super().__init__(config, "resource_controller")
        self._last_metrics: MetriquesSystem | None = None

    @log_appel()
    @metriques("resources.collect")
    @retry(nb_tentatives=2, delai_initial=0.5, backoff=2.0)
    async def collecter_metriques(self) -> MetriquesSystem:
        cpu_count = os.cpu_count() or 1
        load_avg = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.0
        cpu_usage = min(100.0, (load_avg / cpu_count) * 100.0)

        metrics = MetriquesSystem(
            cpu_usage=cpu_usage,
            ram_usage=0.0,
            alertes_par_seconde=0.0,
            alertes_en_queue=0,
            uptime_secondes=0,
            erreurs_recentes=0,
            metadata={"source": "resource_controller"},
        )
        self._last_metrics = metrics
        return metrics

    @log_appel()
    @metriques("resources.thresholds")
    async def verifier_limites(self) -> ConditionSante:
        metrics = self._last_metrics or await self.collecter_metriques()
        cpu_limit = float(self._config.obtenir("raspberry_pi.cpu_limit_percent", 70))
        ram_limit = float(self._config.obtenir("raspberry_pi.ram_limit_percent", 70))
        cpu_ok = metrics.cpu_usage <= cpu_limit
        ram_ok = metrics.ram_usage <= ram_limit
        sain = cpu_ok and ram_ok
        return ConditionSante(
            nom_composant=self.nom_composant,
            sain=sain,
            message="OK" if sain else "Depassement ressources",
            details={
                "cpu_usage": metrics.cpu_usage,
                "ram_usage": metrics.ram_usage,
                "cpu_limit": cpu_limit,
                "ram_limit": ram_limit,
            },
        )

    @log_appel()
    async def enregistrer(self, nom: str, valeur: float) -> None:
        if not self._last_metrics:
            self._last_metrics = MetriquesSystem(metadata={})
        self._last_metrics.metadata[nom] = valeur


__all__ = ["ResourceController"]
