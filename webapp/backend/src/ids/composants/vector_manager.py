"""VectorManager - gestion de la configuration Vector."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..app.decorateurs import log_appel, metriques
from ..domain import ConditionSante
from .base import BaseComponent

if TYPE_CHECKING:
    from ..interfaces import GestionnaireConfig


class VectorManager(BaseComponent):
    """Composant pour Vector (lecture eve.json -> OpenSearch)."""

    def __init__(self, config: GestionnaireConfig | None = None) -> None:
        super().__init__(config, "vector")
        config_path = "webapp/db/config/vector.toml"
        if config:
            config_path = config.obtenir("vector.config_path", config_path)
        self._config_path = Path(config_path)

    @log_appel()
    @metriques("vector.config.validate")
    async def verifier_config(self) -> bool:
        return self._config_path.exists()

    @log_appel()
    @metriques("vector.health")
    async def verifier_sante(self) -> ConditionSante:
        base = await super().verifier_sante()
        if not self._config_path.exists():
            return ConditionSante(
                nom_composant=self.nom,
                sain=False,
                message="config manquante",
                details={"config_path": str(self._config_path)},
            )
        details = dict(base.details)
        details["config_path"] = str(self._config_path)
        return ConditionSante(
            nom_composant=base.nom_composant,
            sain=base.sain,
            message=base.message,
            details=details,
        )


__all__ = ["VectorManager"]
