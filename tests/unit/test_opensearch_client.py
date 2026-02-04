"""Tests unitaires pour le client OpenSearch."""

from unittest.mock import Mock, patch

from opensearchpy import AWSV4SignerAuth, RequestsHttpConnection

from ids.infrastructure.opensearch_client import OpenSearchClient


class DummyConfig:
    """Config minimale pour les tests."""

    def __init__(self, data):
        self._data = data

    def obtenir(self, cle, defaut=None):
        valeur = self._data
        for partie in cle.split("."):
            if isinstance(valeur, dict) and partie in valeur:
                valeur = valeur[partie]
            else:
                return defaut
        return valeur


def test_opensearch_client_builds_sigv4_client(aws_config):
    config = DummyConfig(aws_config)
    session = Mock()
    session.get_credentials.return_value = Mock()

    with patch(
        "ids.infrastructure.opensearch_client.boto3.Session", return_value=session
    ) as session_cls:
        with patch("ids.infrastructure.opensearch_client.OpenSearch") as opensearch_cls:
            opensearch_instance = Mock()
            opensearch_cls.return_value = opensearch_instance

            client = OpenSearchClient(config)
            assert client.client is opensearch_instance

            session_cls.assert_called_once_with(region_name="eu-west-1")
            _, kwargs = opensearch_cls.call_args
            assert kwargs["hosts"] == [
                {"host": "search-ids2-test.eu-west-1.es.amazonaws.com", "port": 443}
            ]
            assert kwargs["use_ssl"] is True
            assert isinstance(kwargs["http_auth"], AWSV4SignerAuth)
            assert kwargs["connection_class"] is RequestsHttpConnection


def test_opensearch_client_ping_returns_false_without_endpoint():
    client = OpenSearchClient(DummyConfig({}))
    assert client.ping() is False


def test_opensearch_client_ping_calls_client(aws_config):
    config = DummyConfig(aws_config)
    session = Mock()
    session.get_credentials.return_value = Mock()

    with patch("ids.infrastructure.opensearch_client.boto3.Session", return_value=session):
        with patch("ids.infrastructure.opensearch_client.OpenSearch") as opensearch_cls:
            opensearch_instance = Mock()
            opensearch_instance.ping.return_value = True
            opensearch_cls.return_value = opensearch_instance

            client = OpenSearchClient(config)
            assert client.ping(timeout=1.5) is True
            opensearch_instance.ping.assert_called_once_with(request_timeout=1.5)
