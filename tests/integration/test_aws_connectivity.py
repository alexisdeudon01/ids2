"""Tests d'intégration pour la connectivité AWS."""

from typing import Any, Dict
from unittest.mock import MagicMock, Mock, patch

import pytest


class TestAWSConnectivity:
    """Tests de connectivité AWS avec mocks."""

    def test_aws_credentials_available(self, mock_boto3_session):
        """Test que les credentials AWS sont disponibles."""
        creds = mock_boto3_session.get_credentials()

        assert creds.access_key is not None
        assert creds.secret_key is not None
        assert mock_boto3_session.region_name == "eu-west-1"

    def test_opensearch_client_ping(self, mock_opensearch_client):
        """Test ping vers OpenSearch."""
        assert mock_opensearch_client.ping() is True

    def test_opensearch_cluster_health(self, mock_opensearch_client):
        """Test health check du cluster OpenSearch."""
        health = mock_opensearch_client.cluster.health()

        assert health["status"] in ["green", "yellow", "red"]
        assert health["status"] == "green"

    def test_opensearch_version_info(self, mock_opensearch_client):
        """Test récupération des infos de version."""
        info = mock_opensearch_client.info()

        assert "version" in info
        assert "number" in info["version"]


class TestAWSConfigValidation:
    """Tests de validation de la configuration AWS."""

    def test_aws_region_configured(self, aws_config: Dict[str, Any]):
        """Test que la région AWS est configurée."""
        assert aws_config["aws"]["region"] == "eu-west-1"

    def test_opensearch_endpoint_configured(self, aws_config: Dict[str, Any]):
        """Test que l'endpoint OpenSearch est configuré."""
        endpoint = aws_config["aws"]["opensearch"]["endpoint"]

        assert endpoint.startswith("https://")
        assert "es.amazonaws.com" in endpoint

    def test_opensearch_index_prefix(self, aws_config: Dict[str, Any]):
        """Test le préfixe d'index OpenSearch."""
        prefix = aws_config["aws"]["opensearch"]["index_prefix"]

        assert prefix == "ids2-alerts-"

    def test_bulk_size_positive(self, aws_config: Dict[str, Any]):
        """Test que bulk_size est positif."""
        bulk_size = aws_config["aws"]["opensearch"]["bulk_size"]

        assert bulk_size > 0
        assert bulk_size == 100

    def test_invalid_aws_config_detection(self, invalid_aws_config: Dict[str, Any]):
        """Test détection de config AWS invalide."""
        aws = invalid_aws_config["aws"]

        # Région vide
        assert aws["region"] == ""

        # Endpoint non HTTPS
        assert not aws["opensearch"]["endpoint"].startswith("https://")

        # bulk_size négatif
        assert aws["opensearch"]["bulk_size"] < 0


class TestSigV4Authentication:
    """Tests pour l'authentification SigV4."""

    def test_sigv4_auth_creation(self, mock_boto3_session):
        """Test création d'un auth SigV4."""
        creds = mock_boto3_session.get_credentials()
        region = mock_boto3_session.region_name

        # Simuler la création d'auth SigV4
        auth_config = {
            "access_key": creds.access_key,
            "secret_key": creds.secret_key,
            "region": region,
            "service": "es",
        }

        assert auth_config["access_key"] is not None
        assert auth_config["region"] == "eu-west-1"
        assert auth_config["service"] == "es"

    def test_instance_profile_mode(self, aws_config: Dict[str, Any]):
        """Test mode instance profile."""
        use_instance_profile = aws_config["aws"]["credentials"]["use_instance_profile"]

        assert use_instance_profile is True


class TestOpenSearchOperations:
    """Tests des opérations OpenSearch."""

    def test_index_alert_mock(self, mock_opensearch_client):
        """Test indexation d'une alerte (mock)."""
        mock_opensearch_client.index = Mock(return_value={"result": "created"})

        alert = {
            "timestamp": "2026-02-02T22:00:00Z",
            "source_ip": "192.168.1.100",
            "dest_ip": "10.0.0.1",
            "signature": "ET SCAN Potential SSH Scan",
            "severity": 2,
        }

        result = mock_opensearch_client.index(index="ids2-alerts-2026.02.02", body=alert)

        assert result["result"] == "created"
        mock_opensearch_client.index.assert_called_once()

    def test_bulk_index_mock(self, mock_opensearch_client):
        """Test indexation bulk (mock)."""
        mock_opensearch_client.bulk = Mock(
            return_value={"took": 30, "errors": False, "items": [{"index": {"status": 201}}] * 10}
        )

        alerts = [{"alert": f"test_{i}"} for i in range(10)]

        result = mock_opensearch_client.bulk(body=alerts)

        assert result["errors"] is False
        assert len(result["items"]) == 10

    def test_search_alerts_mock(self, mock_opensearch_client):
        """Test recherche d'alertes (mock)."""
        mock_opensearch_client.search = Mock(
            return_value={
                "hits": {
                    "total": {"value": 5},
                    "hits": [{"_source": {"severity": i}} for i in range(5)],
                }
            }
        )

        result = mock_opensearch_client.search(
            index="ids2-alerts-*", body={"query": {"match_all": {}}}
        )

        assert result["hits"]["total"]["value"] == 5
        assert len(result["hits"]["hits"]) == 5
