"""
fixtures/config_fixtures.py - Fixtures pour les tests de configuration.
"""

import sys
from pathlib import Path
from typing import Any, Dict

import pytest

# Ajouter src à PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ids.config.loader import ConfigManager
from ids.domain import ConfigurationIDS


@pytest.fixture
def config_dict_test() -> Dict[str, Any]:
    """Configuration de test complète."""
    return {
        "version": "2.0.0",
        "interface_reseau": "eth0",
        "repertoire_logs": "/tmp/test_logs",
        "repertoire_config": "/tmp/test_config",
        "suricata": {
            "config_path": "/tmp/suricata.yaml",
            "log_path": "/tmp/eve.json",
            "eve_log_options": {
                "payload": False,
                "packet": False,
                "http": True,
                "dns": True,
                "tls": True,
            },
        },
        "redis": {
            "host": "localhost",
            "port": 6379,
            "db": 0,
        },
        "aws": {
            "region": "eu-west-1",
            "opensearch_domain": "test-opensearch",
            "opensearch_endpoint": None,
        },
        "docker": {
            "compose_path": "docker/docker-compose.yml",
        },
        "ressources": {
            "cpu_limit_percent": 80.0,
            "ram_limit_percent": 85.0,
            "throttling_enabled": True,
        },
    }


@pytest.fixture
def config_ids_test(config_dict_test) -> ConfigurationIDS:
    """ConfigurationIDS pour les tests."""
    return ConfigurationIDS(
        version=config_dict_test["version"],
        interface_reseau=config_dict_test["interface_reseau"],
        repertoire_logs=config_dict_test["repertoire_logs"],
        suricata_config_path=config_dict_test["suricata"]["config_path"],
        suricata_log_path=config_dict_test["suricata"]["log_path"],
        redis_host=config_dict_test["redis"]["host"],
        redis_port=config_dict_test["redis"]["port"],
        aws_region=config_dict_test["aws"]["region"],
        cpu_limit_percent=config_dict_test["ressources"]["cpu_limit_percent"],
        ram_limit_percent=config_dict_test["ressources"]["ram_limit_percent"],
    )


@pytest.fixture
def config_manager_test(tmp_path, config_dict_test) -> ConfigManager:
    """ConfigManager pré-configuré pour les tests."""
    import yaml

    config_file = tmp_path / "config_test.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_dict_test, f)

    secret_file = tmp_path / "secret.json"
    secret_file.write_text(
        '{"aws": {"access_key_id": "AKIA_TEST", "secret_access_key": "SECRET_TEST"}}',
        encoding="utf-8",
    )

    return ConfigManager(str(config_file), secret_path=str(secret_file))


@pytest.fixture
def config_minimal() -> ConfigurationIDS:
    """Configuration minimale avec défauts."""
    return ConfigurationIDS()


@pytest.fixture
def config_factory():
    """Factory pour créer des configurations personnalisées."""

    def _create(**overrides) -> ConfigurationIDS:
        defaults = {
            "version": "2.0.0",
            "interface_reseau": "eth0",
            "repertoire_logs": "/tmp/logs",
        }
        defaults.update(overrides)
        return ConfigurationIDS(**defaults)

    return _create


__all__ = [
    "config_dict_test",
    "config_ids_test",
    "config_manager_test",
    "config_minimal",
    "config_factory",
]
