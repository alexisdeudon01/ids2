"""
Interface AlerteSource - Contrat pour les sources d'alertes.

Définit le Protocol pour les sources d'alertes IDS (Suricata, fichiers, API, etc.).
"""

from typing import AsyncGenerator, Protocol

from ..domain.alerte import AlerteIDS


class AlerteSource(Protocol):
    """
    Interface pour une source d'alertes IDS.

    Implémentée par SuricataManager, mais peut être remplacée par
    une autre source (fichier, API, etc.) sans modifier le code client.
    """

    async def fournir_alertes(self) -> AsyncGenerator[AlerteIDS, None]:
        """
        Fournit un flux continu d'alertes.

        Yields:
            AlerteIDS: Les alertes générées par la source

        Raises:
            AlerteSourceIndisponible: Si la source devient indisponible
        """
        ...

    async def valider_connexion(self) -> bool:
        """
        Valide la connexion à la source d'alertes.

        Returns:
            bool: True si la source est opérationnelle, False sinon
        """
        ...

    async def arreter(self) -> None:
        """Arrête proprement la source d'alertes."""
        ...


__all__ = [
    "AlerteSource",
]
