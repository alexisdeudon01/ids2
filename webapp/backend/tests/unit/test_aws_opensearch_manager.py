"""Tests unitaires pour AWSOpenSearchManager."""

from unittest.mock import Mock, patch

import pytest

from ids.infrastructure.aws_manager import AWSOpenSearchManager


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


def test_creer_domaine_requires_domain_name():
    manager = AWSOpenSearchManager(DummyConfig({}))
    with pytest.raises(ValueError):
        manager.creer_domaine()


def test_creer_domaine_uses_config_values():
    config = DummyConfig(
        {
            "aws": {
                "region": "eu-west-1",
                "domain_name": "ids2-domain",
                "opensearch": {
                    "domain": {
                        "engine_version": "OpenSearch_2.11",
                        "cluster_config": {"InstanceType": "t3.small.search", "InstanceCount": 1},
                        "ebs_options": {"EBSEnabled": True, "VolumeSize": 10, "VolumeType": "gp3"},
                    }
                },
            }
        }
    )
    session = Mock()
    opensearch_client = Mock()
    session.client.return_value = opensearch_client

    with patch("ids.infrastructure.aws_manager.boto3.Session", return_value=session):
        manager = AWSOpenSearchManager(config)
        manager.creer_domaine()

    opensearch_client.create_domain.assert_called_once_with(
        DomainName="ids2-domain",
        EngineVersion="OpenSearch_2.11",
        ClusterConfig={"InstanceType": "t3.small.search", "InstanceCount": 1},
        EBSOptions={"EBSEnabled": True, "VolumeSize": 10, "VolumeType": "gp3"},
    )


@pytest.mark.asyncio
async def test_verifier_connexion_uses_opensearch_client():
    config = DummyConfig(
        {
            "aws": {
                "region": "eu-west-1",
                "opensearch": {"endpoint": "https://search.example.com"},
            }
        }
    )
    manager = AWSOpenSearchManager(config)
    manager._client = Mock()
    manager._client.ping.return_value = True

    assert await manager.verifier_connexion(timeout=1.0) is True
    manager._client.ping.assert_called_once_with(timeout=1.0)
