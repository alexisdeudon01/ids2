"""
Protocol for alert persistence.
"""

from typing import Optional, Protocol

from ..domain import AlerteIDS


class PersistanceAlertes(Protocol):
    """Alert persistence interface."""

    async def sauvegarder(self, alerte: AlerteIDS) -> None:
        """Persist an alert."""

        ...

    async def recuperer(self, id_alerte: str) -> Optional[AlerteIDS]:
        """Fetch an alert by id."""

        ...

    async def lister_recentes(self, nb: int = 100) -> list[AlerteIDS]:
        """List recent alerts."""

        ...


__all__ = ["PersistanceAlertes"]
"""
Interface PersistanceAlertes - Contrat pour la persistance d'alertes.

Définit le Protocol pour les systèmes de stockage d'alertes.
"""

from typing import List, Optional, Protocol

from ..domain import AlerteIDS


class PersistanceAlertes(Protocol):
    """Interface pour la persistance d'alertes."""

    async def sauvegarder(self, alerte: AlerteIDS) -> None:
        """Sauvegarde une alerte."""
        ...

    async def recuperer(self, id_alerte: str) -> Optional[AlerteIDS]:
        """Récupère une alerte par son ID."""
        ...

    async def lister_recentes(self, nb: int = 100) -> List[AlerteIDS]:
        """Liste les alertes récentes."""
        ...


__all__ = [
    "PersistanceAlertes",
]
