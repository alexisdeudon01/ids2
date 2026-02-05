"""Tests for deployment configuration."""

import os
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "webbapp"))

import unittest
from ids.deploy.config import DeployConfig


class TestDeployConfig(unittest.TestCase):
    """Test DeployConfig dataclass."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        config = DeployConfig(elastic_password="test123")
        
        self.assertEqual(config.aws_region, "eu-west-1")
        self.assertEqual(config.pi_host, "sinik")
        self.assertEqual(config.pi_ip, "192.168.178.66")
        self.assertEqual(config.pi_user, "pi")
        self.assertEqual(config.pi_password, "pi")
        self.assertEqual(config.sudo_password, "pi")
        self.assertEqual(config.remote_dir, "/opt/ids2")
        self.assertEqual(config.mirror_interface, "eth0")
        self.assertEqual(config.elastic_password, "test123")
        self.assertEqual(config.ssh_key_path, "/home/tor/.ssh/pi_key")

    def test_custom_values(self):
        """Test that custom values override defaults."""
        config = DeployConfig(
            elastic_password="custom_pwd",
            aws_region="us-east-1",
            pi_host="10.0.0.1",
            pi_user="admin",
            remote_dir="/custom/path",
            ssh_key_path="/home/test/.ssh/id_ed25519",
        )
        
        self.assertEqual(config.aws_region, "us-east-1")
        self.assertEqual(config.pi_host, "10.0.0.1")
        self.assertEqual(config.pi_user, "admin")
        self.assertEqual(config.remote_dir, "/custom/path")
        self.assertEqual(config.elastic_password, "custom_pwd")
        self.assertEqual(config.ssh_key_path, "/home/test/.ssh/id_ed25519")

    def test_boolean_flags(self):
        """Test boolean flags default to False."""
        config = DeployConfig(elastic_password="test")
        
        self.assertFalse(config.reset_first)
        self.assertFalse(config.install_docker)
        self.assertFalse(config.remove_docker)

    def test_aws_credentials_from_env(self):
        """Test AWS credentials default to environment variables."""
        with mock.patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "test_key", "AWS_SECRET_ACCESS_KEY": "test_secret"}):
            config = DeployConfig(elastic_password="test")

        self.assertEqual(config.aws_access_key_id, "test_key")
        self.assertEqual(config.aws_secret_access_key, "test_secret")

    def test_boolean_flags_custom(self):
        """Test boolean flags can be set to True."""
        config = DeployConfig(
            elastic_password="test",
            reset_first=True,
            install_docker=True
        )
        
        self.assertTrue(config.reset_first)
        self.assertTrue(config.install_docker)
        self.assertFalse(config.remove_docker)


if __name__ == "__main__":
    unittest.main()
