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
        self.assertEqual(config.aws_ami_id, "")
        self.assertEqual(config.aws_instance_type, "t3.medium")
        self.assertEqual(config.aws_key_name, "")
        self.assertEqual(config.aws_subnet_id, "")
        self.assertEqual(config.aws_vpc_id, "")
        self.assertEqual(config.aws_security_group_id, "")
        self.assertEqual(config.aws_iam_instance_profile, "")
        self.assertEqual(config.aws_private_key_path, "")
        self.assertEqual(config.aws_root_volume_gb, 30)
        self.assertEqual(config.aws_root_volume_type, "gp3")
        self.assertTrue(config.aws_associate_public_ip)

    def test_custom_values(self):
        """Test that custom values override defaults."""
        config = DeployConfig(
            elastic_password="custom_pwd",
            aws_region="us-east-1",
            pi_host="10.0.0.1",
            pi_user="admin",
            remote_dir="/custom/path",
            ssh_key_path="/home/test/.ssh/id_ed25519",
            aws_ami_id="ami-123",
            aws_instance_type="t3.large",
            aws_key_name="my-key",
            aws_subnet_id="subnet-123",
            aws_vpc_id="vpc-456",
            aws_security_group_id="sg-123",
            aws_iam_instance_profile="MyProfile",
            aws_private_key_path="/home/test/.ssh/aws.pem",
            aws_root_volume_gb=50,
            aws_root_volume_type="gp2",
            aws_associate_public_ip=False,
        )
        
        self.assertEqual(config.aws_region, "us-east-1")
        self.assertEqual(config.pi_host, "10.0.0.1")
        self.assertEqual(config.pi_user, "admin")
        self.assertEqual(config.remote_dir, "/custom/path")
        self.assertEqual(config.elastic_password, "custom_pwd")
        self.assertEqual(config.ssh_key_path, "/home/test/.ssh/id_ed25519")
        self.assertEqual(config.aws_ami_id, "ami-123")
        self.assertEqual(config.aws_instance_type, "t3.large")
        self.assertEqual(config.aws_key_name, "my-key")
        self.assertEqual(config.aws_subnet_id, "subnet-123")
        self.assertEqual(config.aws_vpc_id, "vpc-456")
        self.assertEqual(config.aws_security_group_id, "sg-123")
        self.assertEqual(config.aws_iam_instance_profile, "MyProfile")
        self.assertEqual(config.aws_private_key_path, "/home/test/.ssh/aws.pem")
        self.assertEqual(config.aws_root_volume_gb, 50)
        self.assertEqual(config.aws_root_volume_type, "gp2")
        self.assertFalse(config.aws_associate_public_ip)

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
