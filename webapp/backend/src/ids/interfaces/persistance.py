"""
Interface PersistanceAlertes - Contrat pour la persistance d'alertes.

Définit le Protocol pour les systèmes de stockage d'alertes.
"""

from typing import Protocol

from ..domain import AlerteIDS


class PersistanceAlertes(Protocol):
    """Interface pour la persistance d'alertes."""

    async def sauvegarder(self, alerte: AlerteIDS) -> None:
        """Sauvegarde une alerte."""
        ...

    async def recuperer(self, id_alerte: str) -> AlerteIDS | None:
        """Récupère une alerte par son ID."""
        ...

    async def lister_recentes(self, nb: int = 100) -> list[AlerteIDS]:
        """Liste les alertes récentes."""
        ...


__all__ = ["PersistanceAlertes"]
