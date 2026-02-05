"""Deployment configuration."""

from dataclasses import dataclass, field


@dataclass
class DeployConfig:
    """Configuration for IDS deployment."""
    
    elastic_password: str
    aws_region: str = "eu-west-1"
    pi_host: str = "192.168.178.66"
    pi_user: str = "pi"
    pi_password: str = "pi"
    sudo_password: str = "pi"
    remote_dir: str = "/opt/ids2"
    mirror_interface: str = "eth0"  # Network interface for port mirroring
    reset_first: bool = False
    install_docker: bool = False
    remove_docker: bool = False
