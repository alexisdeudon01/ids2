"""
fixtures/container_fixtures.py - Fixtures pour le conteneur DI.
"""

import sys
from pathlib import Path
from typing import Any, Dict

import pytest

# Ajouter src à PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ids.app.container import ConteneurDI, ConteneurFactory
from ids.config.loader import ConfigManager
from ids.domain import ConfigurationIDS


@pytest.fixture
def container_di_test(config_dict_test: Dict[str, Any]) -> ConteneurDI:
    """Conteneur DI préconfigurée pour les tests."""
    container = ConteneurDI()

    # Enregistrer la configuration
    container.enregistrer_singleton(
        ConfigurationIDS,
        ConfigurationIDS(
            **{
                k: v
                for k, v in config_dict_test.items()
                if k in ConfigurationIDS.__dataclass_fields__
            }
        ),
    )

    return container


@pytest.fixture
def container_factory():
    """Factory pour créer des conteneurs personnalisés."""

    def _create(config: Dict[str, Any] = None) -> ConteneurDI:
        container = ConteneurDI()
        if config:
            container.enregistrer_services(config)
        return container

    return _create


__all__ = [
    "container_di_test",
    "container_factory",
]
