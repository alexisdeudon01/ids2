"""Tests for AWS deployer."""

import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "webbapp"))


class TestAWSDeployer(unittest.TestCase):
    """Validate AWS deployer behavior with mocked boto3."""

    def _load_module(self):
        fake_resource = mock.MagicMock()
        fake_session = mock.MagicMock()
        fake_session.resource.return_value = fake_resource
        fake_session.client.return_value = mock.MagicMock()
        fake_boto3 = types.SimpleNamespace(
            Session=mock.MagicMock(return_value=fake_session),
            resource=mock.MagicMock(return_value=fake_resource),
            client=mock.MagicMock(return_value=mock.MagicMock()),
        )
        fake_requests = mock.MagicMock()
        fake_elasticsearch = types.SimpleNamespace(Elasticsearch=mock.MagicMock())

        with mock.patch.dict(
            sys.modules,
            {
                "boto3": fake_boto3,
                "requests": fake_requests,
                "elasticsearch": fake_elasticsearch,
            },
        ):
            sys.modules.pop("ids.deploy.aws_deployer", None)
            module = importlib.import_module("ids.deploy.aws_deployer")

        return module, fake_boto3, fake_resource, fake_session

    def test_uses_session_with_credentials(self):
        module, fake_boto3, _, fake_session = self._load_module()

        module.AWSDeployer(
            "eu-west-1",
            "pwd",
            lambda msg: None,
            aws_access_key_id="AKIA_TEST",
            aws_secret_access_key="SECRET_TEST",
            ami_id="ami-123",
        )

        fake_boto3.Session.assert_called_once_with(
            aws_access_key_id="AKIA_TEST",
            aws_secret_access_key="SECRET_TEST",
            region_name="eu-west-1",
        )
        fake_session.resource.assert_called_once_with("ec2")
        fake_session.client.assert_any_call("ssm")
        fake_session.client.assert_any_call("ec2")

    def test_uses_resource_without_credentials(self):
        module, fake_boto3, _, _ = self._load_module()

        module.AWSDeployer("eu-west-1", "pwd", lambda msg: None, ami_id="ami-123")

        fake_boto3.Session.assert_called_once_with(region_name="eu-west-1")

    def test_list_instances_summary(self):
        module, _, fake_resource, _ = self._load_module()

        fake_instance = mock.MagicMock()
        fake_instance.id = "i-123"
        fake_instance.state = {"Name": "running"}
        fake_instance.public_ip_address = "1.2.3.4"
        fake_instance.private_ip_address = "10.0.0.1"
        fake_resource.instances.all.return_value = [fake_instance]

        deployer = module.AWSDeployer("eu-west-1", "pwd", lambda msg: None, ami_id="ami-123")
        instances = deployer.list_instances()

        self.assertEqual(
            instances,
            [
                {
                    "id": "i-123",
                    "state": "running",
                    "public_ip": "1.2.3.4",
                    "private_ip": "10.0.0.1",
                }
            ],
        )

    def test_estimate_costs(self):
        module, _, _, _ = self._load_module()
        deployer = module.AWSDeployer("eu-west-1", "pwd", lambda msg: None, ami_id="ami-123")
        costs = deployer.estimate_costs("t3.medium", "eu-west-1")
        self.assertGreater(costs["ec2_hourly_usd"], 0)
        self.assertGreater(costs["total_monthly_usd"], 0)
