"""Integration tests for deployment orchestrator."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "webbapp"))

import unittest
from ids.deploy.config import DeployConfig


class TestDeploymentIntegration(unittest.TestCase):
    """Integration tests for deployment."""

    def test_config_creation_minimal(self):
        """Test creating config with minimal parameters."""
        config = DeployConfig(elastic_password="secure_password")
        
        # Verify all defaults are set
        self.assertIsNotNone(config.aws_region)
        self.assertIsNotNone(config.pi_host)
        self.assertIsNotNone(config.pi_user)
        self.assertIsNotNone(config.remote_dir)
        self.assertIsNotNone(config.mirror_interface)

    def test_config_full_customization(self):
        """Test creating config with all custom values."""
        config = DeployConfig(
            elastic_password="my_password",
            aws_region="us-west-2",
            pi_host="192.168.1.100",
            pi_user="admin",
            pi_password="admin_pass",
            sudo_password="sudo_pass",
            remote_dir="/custom/dir",
            mirror_interface="wlan0",
            reset_first=True,
            install_docker=True,
            remove_docker=False,
            aws_access_key_id="access",
            aws_secret_access_key="secret",
        )
        
        self.assertEqual(config.elastic_password, "my_password")
        self.assertEqual(config.aws_region, "us-west-2")
        self.assertEqual(config.pi_host, "192.168.1.100")
        self.assertEqual(config.pi_user, "admin")
        self.assertEqual(config.remote_dir, "/custom/dir")
        self.assertEqual(config.mirror_interface, "wlan0")
        self.assertTrue(config.reset_first)
        self.assertTrue(config.install_docker)
        self.assertFalse(config.remove_docker)
        self.assertEqual(config.aws_access_key_id, "access")
        self.assertEqual(config.aws_secret_access_key, "secret")

    def test_lazy_import_config(self):
        """Test that config can be imported via lazy loading."""
        from ids.deploy import DeployConfig as LazyConfig
        
        config = LazyConfig(elastic_password="test")
        self.assertEqual(config.pi_host, "es-sink")


if __name__ == "__main__":
    unittest.main()
