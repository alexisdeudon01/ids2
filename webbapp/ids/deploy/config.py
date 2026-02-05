"""Deployment configuration."""

import os
from dataclasses import dataclass, field


@dataclass
class DeployConfig:
    """Configuration for IDS deployment."""
    
    elastic_password: str
    aws_region: str = "eu-west-1"
    aws_access_key_id: str = field(default_factory=lambda: os.getenv("AWS_ACCESS_KEY_ID", ""))
    aws_secret_access_key: str = field(default_factory=lambda: os.getenv("AWS_SECRET_ACCESS_KEY", ""))
    aws_ami_id: str = field(default_factory=lambda: os.getenv("IDS_AWS_AMI_ID", ""))
    ssh_key_path: str = field(default_factory=lambda: os.getenv("IDS_SSH_KEY_PATH", "/home/tor/.ssh/pi_key"))
    pi_host: str = "sinik"
    pi_ip: str = "192.168.178.66"
    pi_user: str = "pi"
    pi_password: str = "pi"
    sudo_password: str = "pi"
    remote_dir: str = "/opt/ids2"
    mirror_interface: str = "eth0"  # Network interface for port mirroring
    reset_first: bool = False
    install_docker: bool = False
    remove_docker: bool = False
