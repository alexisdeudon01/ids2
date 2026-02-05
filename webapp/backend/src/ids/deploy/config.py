"""Deployment configuration."""

from dataclasses import dataclass


@dataclass
class DeployConfig:
    """Configuration for IDS deployment."""
    
    aws_region: str
    elastic_password: str
    pi_host: str
    pi_user: str
    pi_password: str
    sudo_password: str
    remote_dir: str
    mirror_interface: str
    reset_first: bool = False
    install_docker: bool = False
    remove_docker: bool = False
