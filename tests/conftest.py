"""
conftest.py - Fixtures et configuration globale pytest.

Centralise les fixtures réutilisables pour tous les tests.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest

# Importer les fixtures depuis les modules spécialisés
from fixtures.alerte_fixtures import (
    alerte_ids_batch,
    alerte_ids_critique,
    alerte_ids_simple,
)
from fixtures.config_fixtures import (
    config_ids_test,
    config_manager_test,
)
from fixtures.container_fixtures import (
    container_di_test,
)

# ============================================================================
# Fixtures de Base
# ============================================================================


@pytest.fixture(scope="session")
def logger() -> logging.Logger:
    """Logger global pour les tests."""
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    return logging.getLogger("test")


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Répertoire contenant les données de test."""
    return Path(__file__).parent / "data"


@pytest.fixture(scope="session")
def temp_dir(tmp_path_factory) -> Path:
    """Répertoire temporaire pour les tests."""
    return tmp_path_factory.mktemp("ids_test")


@pytest.fixture
def event_loop():
    """Crée une event loop pour chaque test async."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()

    yield loop
    loop.close()


# ============================================================================
# Fixtures de Nettoyage
# ============================================================================


@pytest.fixture(autouse=True)
def reset_logging():
    """Réinitialise la configuration logging après chaque test."""
    yield
    logging.getLogger().handlers.clear()


@pytest.fixture(autouse=True)
def cleanup_temp_files(temp_dir):
    """Nettoie les fichiers temporaires après chaque test."""
    yield
    import shutil

    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)


# ============================================================================
# Hooks Pytest Personnalisés
# ============================================================================


def pytest_configure(config):
    """Configuration initiale de pytest."""
    # Enregistrer des markers additionnels si nécessaire
    pass


def pytest_collection_modifyitems(config, items):
    """Modifie les items collectés (les tests)."""
    for item in items:
        # Marquer les tests async
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)

        # Marquer les tests lents
        if "sleep" in item.get_closest_marker("slow", default=""):
            item.add_marker(pytest.mark.slow)


def pytest_runtest_logreport(report):
    """Hook appelé après chaque test."""
    if report.when == "call":
        if report.passed:
            pass  # Test réussi
        elif report.failed:
            pass  # Test échoué
        elif report.skipped:
            pass  # Test ignoré


# ============================================================================
# Markers Personnalisés pour Filtrage
# ============================================================================


def pytest_addoption(parser):
    """Ajoute des options de ligne de commande."""
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Exécuter aussi les tests d'intégration",
    )
    parser.addoption(
        "--slow", action="store_true", default=False, help="Exécuter aussi les tests lents"
    )


# ==============================================================================
# Fixtures Infrastructure (AWS, Config Validator)
# ==============================================================================

from fixtures.infra_fixtures import (
    aws_config,
    invalid_aws_config,
    invalid_config_yaml,
    mock_boto3_session,
    mock_config_file,
    mock_invalid_config_file,
    mock_opensearch_client,
    valid_config_yaml,
)
