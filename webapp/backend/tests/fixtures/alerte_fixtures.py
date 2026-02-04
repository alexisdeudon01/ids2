"""
fixtures/alerte_fixtures.py - Fixtures pour les tests d'AlerteIDS.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import List

import pytest

# Ajouter src à PYTHONPATH pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ids.domain import AlerteIDS, SeveriteAlerte, TypeAlerte


@pytest.fixture
def alerte_ids_simple() -> AlerteIDS:
    """Une alerte simple pour les tests de base."""
    return AlerteIDS(
        timestamp=datetime.utcnow(),
        severite=SeveriteAlerte.MOYENNE,
        type_alerte=TypeAlerte.INTRUSION,
        source_ip="192.168.1.100",
        destination_ip="10.0.0.1",
        port=443,
        protocole="TCP",
        signature="ET MALWARE",
        description="Tentative de connexion suspecte",
        metadata={"hostname": "attacker.local"},
    )


@pytest.fixture
def alerte_ids_critique() -> AlerteIDS:
    """Une alerte critique pour les tests de sévérité."""
    return AlerteIDS(
        timestamp=datetime.utcnow(),
        severite=SeveriteAlerte.CRITIQUE,
        type_alerte=TypeAlerte.INTRUSION,
        source_ip="203.0.113.45",  # IP publique suspecte
        destination_ip="10.0.0.50",
        port=22,
        protocole="TCP",
        signature="ET MALWARE SQL Injection Attempt",
        description="Attaque SQL Injection détectée",
        metadata={
            "hostname": "external-attacker",
            "country": "Unknown",
            "threat_level": "critical",
        },
    )


@pytest.fixture
def alerte_ids_batch() -> List[AlerteIDS]:
    """Un lot d'alertes pour les tests de traitement."""
    return [
        AlerteIDS(
            timestamp=datetime.utcnow(),
            severite=SeveriteAlerte.BASSE,
            type_alerte=TypeAlerte.ANOMALIE,
            source_ip=f"192.168.1.{i}",
            destination_ip="10.0.0.1",
            port=80 + i,
            protocole="TCP",
            signature=f"TEST ALERTE {i}",
            description=f"Alerte de test #{i}",
        )
        for i in range(1, 11)  # 10 alertes
    ]


@pytest.fixture
def alerte_ids_tous_types() -> List[AlerteIDS]:
    """Alertes couvrant tous les types."""
    types = [
        TypeAlerte.INTRUSION,
        TypeAlerte.ANOMALIE,
        TypeAlerte.CONFORMITE,
        TypeAlerte.RESSOURCE,
    ]

    return [
        AlerteIDS(
            timestamp=datetime.utcnow(),
            severite=SeveriteAlerte.HAUTE,
            type_alerte=t,
            source_ip="192.168.1.100",
            destination_ip="10.0.0.1",
            port=443,
            protocole="TCP",
            signature=f"ET {t.value.upper()}",
            description=f"Alerte de type {t.value}",
        )
        for t in types
    ]


@pytest.fixture
def alerte_factory():
    """Factory pour créer des alertes personnalisées."""

    def _create(
        source_ip: str = "192.168.1.1",
        destination_ip: str = "10.0.0.1",
        port: int = 443,
        severite: SeveriteAlerte = SeveriteAlerte.MOYENNE,
        type_alerte: TypeAlerte = TypeAlerte.INTRUSION,
        **kwargs,
    ) -> AlerteIDS:
        return AlerteIDS(
            source_ip=source_ip,
            destination_ip=destination_ip,
            port=port,
            severite=severite,
            type_alerte=type_alerte,
            **kwargs,
        )

    return _create


__all__ = [
    "alerte_ids_simple",
    "alerte_ids_critique",
    "alerte_ids_batch",
    "alerte_ids_tous_types",
    "alerte_factory",
]
