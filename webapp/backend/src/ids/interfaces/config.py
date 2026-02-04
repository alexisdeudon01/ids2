"""
Interface GestionnaireConfig - Contrat pour la gestion de configuration.

Définit le Protocol pour les gestionnaires de configuration.
"""

from typing import Any, Protocol


class GestionnaireConfig(Protocol):
    """Interface pour la gestion de configuration."""

    def obtenir(self, key: str, defaut: Any = None) -> Any:
        """Obtient une valeur de configuration."""
        ...

    def definir(self, key: str, valeur: Any) -> None:
        """Définit une valeur de configuration."""
        ...

    def recharger(self) -> None:
        """Recharge la configuration depuis la source."""
        ...

    def get_all(self) -> dict[str, Any]:
        """Retourne la configuration complete."""
        ...

    def get(self, key: str, defaut: Any = None) -> Any:
        """Alias de obtenir() pour compatibilite."""
        ...


__all__ = [
    "GestionnaireConfig",
]
