"""
Interface GestionnaireComposant - Contrat pour les composants gérés.

Définit le Protocol pour tous les composants du système (Suricata, Docker, etc.).
"""

from typing import Protocol

from ..domain import ConditionSante


class GestionnaireComposant(Protocol):
    """
    Interface pour les composants gérés (managers).

    Tous les composants (Suricata, Docker, Metrics, etc.) implémentent
    ce contrat pour un cycle de vie uniforme.
    """

    async def demarrer(self) -> None:
        """
        Démarre le composant.

        Raises:
            ErreurIDS: Si le démarrage échoue
        """
        ...

    async def arreter(self) -> None:
        """Arrête proprement le composant."""
        ...

    async def verifier_sante(self) -> ConditionSante:
        """
        Vérifie l'état de santé du composant.

        Returns:
            ConditionSante: État actuel du composant
        """
        ...

    async def recharger_config(self) -> None:
        """Recharge la configuration du composant."""
        ...


__all__ = ["GestionnaireComposant"]
