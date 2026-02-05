"""Deployment orchestrator facade."""

from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from .aws_deployer import AWSDeployer
from .pi_deployer import PiDeployer
from .ssh_client import SSHClient

if TYPE_CHECKING:
    from .config import DeployConfig


class DeploymentOrchestrator:
    """Orchestrates full IDS deployment."""
    
    def __init__(self, log_callback: Callable[[str], None]) -> None:
        self._log = log_callback

    def full_deploy(self, config: DeployConfig, progress_callback: Callable[[float, str], None]) -> str:
        """Execute full deployment, returns ELK IP."""
        step = 0
        total_steps = 7 + sum([config.reset_first, config.remove_docker, config.install_docker])

        def advance(label: str) -> None:
            nonlocal step
            step += 1
            progress_callback(step / total_steps * 100, label)

        with SSHClient(
            config.pi_host,
            config.pi_user,
            config.pi_password,
            config.sudo_password,
            self._log,
            ssh_key_path=config.ssh_key_path,
        ) as ssh:
            pi = PiDeployer(ssh, config)
            
            advance("Connecting to Pi")
            
            if config.reset_first:
                pi.reset()
                advance("Reset complete")

            if config.remove_docker:
                pi.remove_docker()
                advance("Docker removed")

            if config.install_docker:
                pi.install_docker()
                advance("Docker installed")

            advance("Deploying AWS")
            aws = AWSDeployer(
                config.aws_region,
                config.elastic_password,
                self._log,
                aws_access_key_id=config.aws_access_key_id,
                aws_secret_access_key=config.aws_secret_access_key,
            )
            elk_ip = aws.deploy_elk_stack()

            advance("Configuring Elasticsearch")
            aws.configure_elasticsearch(elk_ip)

            advance("Installing probe")
            pi.install_probe()

            advance("Deploying webapp")
            pi.deploy_webapp()

            advance("Installing streamer")
            pi.install_streamer(elk_ip, config.elastic_password)

            advance("Saving config")
            pi.save_config(elk_ip)

        return elk_ip

    def reset_only(self, config: DeployConfig, progress_callback: Callable[[float, str], None]) -> None:
        """Reset Pi only."""
        progress_callback(5, "Connecting to Pi")
        with SSHClient(
            config.pi_host,
            config.pi_user,
            config.pi_password,
            config.sudo_password,
            self._log,
            ssh_key_path=config.ssh_key_path,
        ) as ssh:
            pi = PiDeployer(ssh, config)
            pi.reset()
        progress_callback(100, "Reset complete")

    def install_docker_only(self, config: DeployConfig, progress_callback: Callable[[float, str], None]) -> None:
        """Install Docker only."""
        progress_callback(10, "Connecting to Pi")
        with SSHClient(
            config.pi_host,
            config.pi_user,
            config.pi_password,
            config.sudo_password,
            self._log,
            ssh_key_path=config.ssh_key_path,
        ) as ssh:
            pi = PiDeployer(ssh, config)
            pi.install_docker()
        progress_callback(100, "Docker installed")

    def remove_docker_only(self, config: DeployConfig, progress_callback: Callable[[float, str], None]) -> None:
        """Remove Docker only."""
        progress_callback(10, "Connecting to Pi")
        with SSHClient(
            config.pi_host,
            config.pi_user,
            config.pi_password,
            config.sudo_password,
            self._log,
            ssh_key_path=config.ssh_key_path,
        ) as ssh:
            pi = PiDeployer(ssh, config)
            pi.remove_docker()
        progress_callback(100, "Docker removed")
