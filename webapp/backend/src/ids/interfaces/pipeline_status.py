"""
Interface pour les providers de statut du pipeline.
"""

from typing import Protocol

from ..domain import ConditionSante


class PipelineStatusProvider(Protocol):
    """Contrat pour fournir le statut d'un composant."""

    nom: str

    async def fournir_statut(self) -> ConditionSante:
        """Retourne l'etat de sante du composant."""
        ...


__all__ = ["PipelineStatusProvider"]
