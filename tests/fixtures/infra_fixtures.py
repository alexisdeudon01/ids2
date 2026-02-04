"""Fixtures pour les tests d'infrastructure (AWS, Config Validator)."""

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest


@pytest.fixture
def mock_boto3_session():
    """Mock d'une session boto3."""
    session = Mock()
    session.get_credentials.return_value = Mock(
        access_key="AKIAIOSFODNN7EXAMPLE",
        secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        token=None,
    )
    session.region_name = "eu-west-1"
    return session


@pytest.fixture
def mock_opensearch_client():
    """Mock du client OpenSearch."""
    client = Mock()
    client.info.return_value = {"version": {"number": "2.11.0"}}
    client.ping.return_value = True
    client.cluster.health.return_value = {"status": "green"}
    return client


@pytest.fixture
def aws_config() -> Dict[str, Any]:
    """Configuration AWS pour les tests."""
    return {
        "aws": {
            "region": "eu-west-1",
            "opensearch": {
                "endpoint": "https://search-ids2-test.eu-west-1.es.amazonaws.com",
                "index_prefix": "ids2-alerts-",
                "bulk_size": 100,
            },
            "credentials": {"use_instance_profile": True},
        }
    }


@pytest.fixture
def invalid_aws_config() -> Dict[str, Any]:
    """Configuration AWS invalide pour tester la validation."""
    return {
        "aws": {
            "region": "",  # Invalid: empty
            "opensearch": {
                "endpoint": "not-a-valid-url",  # Invalid: not HTTPS
                "index_prefix": "",
                "bulk_size": -1,  # Invalid: negative
            },
        }
    }


@pytest.fixture
def valid_config_yaml() -> str:
    """Contenu YAML valide pour les tests."""
    return """
agent:
  name: ids2-agent
  version: "1.0.0"
  log_level: INFO

suricata:
  interface: eth0
  eve_log_path: /mnt/ram_logs/eve.json
  rules_path: /etc/suricata/rules

vector:
  config_path: /etc/vector/vector.toml
  data_dir: /var/lib/vector

aws:
  region: eu-west-1
  opensearch:
    endpoint: https://search-ids2.eu-west-1.es.amazonaws.com
    index_prefix: ids2-alerts-
    bulk_size: 100

resources:
  cpu_threshold: 80
  ram_threshold: 85
  throttle_levels:
    - level: 1
      cpu: 70
      ram: 75
    - level: 2
      cpu: 80
      ram: 85
    - level: 3
      cpu: 90
      ram: 95
"""


@pytest.fixture
def invalid_config_yaml() -> str:
    """Contenu YAML invalide pour les tests."""
    return """
agent:
  name: ""  # Invalid: empty name
  version: 123  # Invalid: should be string
  log_level: INVALID_LEVEL  # Invalid: not a valid level

suricata:
  interface: ""  # Invalid: empty
  eve_log_path: null

resources:
  cpu_threshold: 150  # Invalid: > 100
  ram_threshold: -10  # Invalid: negative
"""


@pytest.fixture
def mock_config_file(tmp_path, valid_config_yaml):
    """Crée un fichier de config temporaire valide."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(valid_config_yaml)
    return config_file


@pytest.fixture
def mock_invalid_config_file(tmp_path, invalid_config_yaml):
    """Crée un fichier de config temporaire invalide."""
    config_file = tmp_path / "invalid_config.yaml"
    config_file.write_text(invalid_config_yaml)
    return config_file
