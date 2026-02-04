"""
Interfaces (Protocol) - contrats sans implementation (DIP).
"""

from typing import Optional, Protocol

from ..domain import MetriquesSystem
from .alerte_source import AlerteSource
from .config import GestionnaireConfig
from .gestionnaire import GestionnaireComposant
from .persistance import PersistanceAlertes
from .pipeline_status import PipelineStatusProvider


class LoggerIDS(Protocol):
    """Interface pour la journalisation."""

    def info(self, message: str) -> None:
        """Loggue une information."""
        ...

    def erreur(self, message: str, exception: Exception | None = None) -> None:
        """Loggue une erreur."""
        ...

    def debug(self, message: str) -> None:
        """Loggue un message de debug."""
        ...


class MetriquesProvider(Protocol):
    """Provider de metriques systeme."""

    async def collecter_metriques(self) -> MetriquesSystem:
        """Collecte les metriques actuelles du systeme."""
        ...


__all__ = [
    "AlerteSource",
    "GestionnaireComposant",
    "GestionnaireConfig",
    "LoggerIDS",
    "MetriquesProvider",
    "PersistanceAlertes",
    "PipelineStatusProvider",
]
