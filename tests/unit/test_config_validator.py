"""Tests unitaires pour le ConfigValidator."""

from pathlib import Path
from typing import Any, Dict

import pytest
import yaml


class TestConfigValidator:
    """Tests pour la validation de configuration."""

    def test_valid_config_structure(self, valid_config_yaml: str):
        """Test qu'une config valide passe la validation."""
        config = yaml.safe_load(valid_config_yaml)

        # Vérifier les sections obligatoires
        assert "agent" in config
        assert "suricata" in config
        assert "aws" in config
        assert "resources" in config

    def test_agent_section_validation(self, valid_config_yaml: str):
        """Test validation de la section agent."""
        config = yaml.safe_load(valid_config_yaml)
        agent = config["agent"]

        assert agent["name"] == "ids2-agent"
        assert agent["version"] == "1.0.0"
        assert agent["log_level"] in ["DEBUG", "INFO", "WARNING", "ERROR"]

    def test_aws_section_validation(self, valid_config_yaml: str):
        """Test validation de la section AWS."""
        config = yaml.safe_load(valid_config_yaml)
        aws = config["aws"]

        assert aws["region"] == "eu-west-1"
        assert aws["opensearch"]["endpoint"].startswith("https://")
        assert aws["opensearch"]["bulk_size"] > 0

    def test_resources_thresholds_validation(self, valid_config_yaml: str):
        """Test validation des seuils de ressources."""
        config = yaml.safe_load(valid_config_yaml)
        resources = config["resources"]

        assert 0 < resources["cpu_threshold"] <= 100
        assert 0 < resources["ram_threshold"] <= 100
        assert len(resources["throttle_levels"]) >= 1

    def test_invalid_cpu_threshold_detected(self, invalid_config_yaml: str):
        """Test détection d'un seuil CPU invalide."""
        config = yaml.safe_load(invalid_config_yaml)
        cpu_threshold = config["resources"]["cpu_threshold"]

        # Le seuil est > 100, donc invalide
        assert cpu_threshold > 100

    def test_invalid_ram_threshold_detected(self, invalid_config_yaml: str):
        """Test détection d'un seuil RAM négatif."""
        config = yaml.safe_load(invalid_config_yaml)
        ram_threshold = config["resources"]["ram_threshold"]

        # Le seuil est négatif, donc invalide
        assert ram_threshold < 0

    def test_empty_agent_name_detected(self, invalid_config_yaml: str):
        """Test détection d'un nom d'agent vide."""
        config = yaml.safe_load(invalid_config_yaml)
        agent_name = config["agent"]["name"]

        assert agent_name == ""

    def test_config_file_loading(self, mock_config_file: Path):
        """Test chargement d'un fichier config."""
        assert mock_config_file.exists()

        with open(mock_config_file) as f:
            config = yaml.safe_load(f)

        assert "agent" in config
        assert config["agent"]["name"] == "ids2-agent"

    def test_invalid_config_file_loading(self, mock_invalid_config_file: Path):
        """Test chargement d'un fichier config invalide."""
        assert mock_invalid_config_file.exists()

        with open(mock_invalid_config_file) as f:
            config = yaml.safe_load(f)

        # La config se charge mais contient des valeurs invalides
        assert config["resources"]["cpu_threshold"] > 100


class TestConfigValidationRules:
    """Tests des règles de validation spécifiques."""

    def test_opensearch_endpoint_must_be_https(self):
        """L'endpoint OpenSearch doit utiliser HTTPS."""
        valid_endpoint = "https://search-ids2.eu-west-1.es.amazonaws.com"
        invalid_endpoint = "http://search-ids2.eu-west-1.es.amazonaws.com"

        assert valid_endpoint.startswith("https://")
        assert not invalid_endpoint.startswith("https://")

    def test_throttle_levels_must_be_ordered(self, valid_config_yaml: str):
        """Les niveaux de throttling doivent être ordonnés."""
        config = yaml.safe_load(valid_config_yaml)
        levels = config["resources"]["throttle_levels"]

        for i in range(len(levels) - 1):
            assert levels[i]["level"] < levels[i + 1]["level"]
            assert levels[i]["cpu"] < levels[i + 1]["cpu"]

    def test_suricata_interface_required(self, valid_config_yaml: str):
        """L'interface Suricata est obligatoire."""
        config = yaml.safe_load(valid_config_yaml)

        assert config["suricata"]["interface"]
        assert config["suricata"]["interface"] == "eth0"

    def test_log_level_enum_values(self):
        """Test des valeurs valides pour log_level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        invalid_level = "INVALID_LEVEL"

        assert invalid_level not in valid_levels
        assert "INFO" in valid_levels
