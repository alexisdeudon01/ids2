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
            ssh_key_path="/home/test/.ssh/id_rsa",
            aws_ami_id="ami-abc",
            aws_instance_type="t3.large",
            aws_key_name="key",
            aws_subnet_id="subnet-123",
            aws_vpc_id="vpc-456",
            aws_security_group_id="sg-123",
            aws_iam_instance_profile="Profile",
            aws_root_volume_gb=40,
            aws_root_volume_type="gp2",
            aws_associate_public_ip=False,
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
        self.assertEqual(config.ssh_key_path, "/home/test/.ssh/id_rsa")
        self.assertEqual(config.aws_ami_id, "ami-abc")
        self.assertEqual(config.aws_instance_type, "t3.large")
        self.assertEqual(config.aws_key_name, "key")
        self.assertEqual(config.aws_subnet_id, "subnet-123")
        self.assertEqual(config.aws_vpc_id, "vpc-456")
        self.assertEqual(config.aws_security_group_id, "sg-123")
        self.assertEqual(config.aws_iam_instance_profile, "Profile")
        self.assertEqual(config.aws_root_volume_gb, 40)
        self.assertEqual(config.aws_root_volume_type, "gp2")
        self.assertFalse(config.aws_associate_public_ip)

    def test_lazy_import_config(self):
        """Test that config can be imported via lazy loading."""
        from ids.deploy import DeployConfig as LazyConfig
        
        config = LazyConfig(elastic_password="test")
        self.assertEqual(config.pi_host, "sinik")


if __name__ == "__main__":
    unittest.main()
