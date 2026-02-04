"""
Persistance d'alertes en memoire (placeholder).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..app.decorateurs import log_appel, metriques
from ..interfaces import PersistanceAlertes

if TYPE_CHECKING:
    from ..domain import AlerteIDS


class InMemoryAlertStore(PersistanceAlertes):
    """Persistance simple en memoire."""

    def __init__(self) -> None:
        self._data: dict[str, AlerteIDS] = {}
        self._order: list[str] = []

    @log_appel()
    @metriques("alertes.sauvegarder")
    async def sauvegarder(self, alerte: AlerteIDS) -> None:
        """Sauvegarde une alerte."""
        key = str(alerte.id)
        self._data[key] = alerte
        self._order.append(key)

    @log_appel()
    @metriques("alertes.recuperer")
    async def recuperer(self, id_alerte: str) -> AlerteIDS | None:
        """Recupere une alerte par ID."""
        return self._data.get(id_alerte)

    @log_appel()
    @metriques("alertes.recentes")
    async def lister_recentes(self, nb: int = 100) -> list[AlerteIDS]:
        """Liste les alertes recentes."""
        ids = self._order[-nb:]
        return [self._data[item_id] for item_id in ids if item_id in self._data]


__all__ = ["InMemoryAlertStore"]
