"""
Metriques et etat de sante du systeme IDS.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class MetriquesSystem:
    """Metriques systeme actuelles."""

    timestamp: datetime = field(default_factory=datetime.utcnow)
    cpu_usage: float = 0.0
    ram_usage: float = 0.0
    alertes_par_seconde: float = 0.0
    alertes_en_queue: int = 0
    uptime_secondes: int = 0
    erreurs_recentes: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConditionSante:
    """Etat de sante d'un composant."""

    nom_composant: str
    sain: bool
    message: str = ""
    derniere_verification: datetime = field(default_factory=datetime.utcnow)
    details: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "ConditionSante",
    "MetriquesSystem",
]
