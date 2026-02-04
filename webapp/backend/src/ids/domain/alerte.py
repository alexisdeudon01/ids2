"""
Entites d'alertes IDS.

Definit les niveaux de severite, types d'alertes et le modele AlerteIDS.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class SeveriteAlerte(Enum):
    """Niveaux de severite des alertes."""

    CRITIQUE = "critique"
    HAUTE = "haute"
    MOYENNE = "moyenne"
    BASSE = "basse"


class TypeAlerte(Enum):
    """Types d'alertes generees par le systeme."""

    INTRUSION = "intrusion"
    ANOMALIE = "anomalie"
    CONFORMITE = "conformite"
    RESSOURCE = "ressource"


@dataclass(frozen=True)
class AlerteIDS:
    """Entite immuable representant une alerte IDS."""

    id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    severite: SeveriteAlerte = SeveriteAlerte.MOYENNE
    type_alerte: TypeAlerte = TypeAlerte.INTRUSION
    source_ip: str = ""
    destination_ip: str = ""
    port: int = 0
    protocole: str = "TCP"
    signature: str = ""
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __hash__(self) -> int:
        return hash((self.id, self.timestamp, self.source_ip))

    def __repr__(self) -> str:
        return (
            f"AlerteIDS(id={self.id.hex[:8]}, "
            f"severite={self.severite.value}, "
            f"{self.source_ip}->{self.destination_ip}:{self.port})"
        )


__all__ = [
    "AlerteIDS",
    "SeveriteAlerte",
    "TypeAlerte",
]
