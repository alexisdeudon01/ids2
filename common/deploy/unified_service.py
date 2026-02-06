"""Unified deployment service - eliminates deploy duplicates."""

import logging
from pathlib import Path
from common.ssh.unified_client import UnifiedSSHClient

logger = logging.getLogger(__name__)


class UnifiedDeploymentService:
    """Unified deployment service for Pi and AWS."""

    def __init__(self, ssh_client: UnifiedSSHClient):
        self.ssh = ssh_client

    def deploy_dockerfile(self, local_dockerfile: str, remote_dir: str = "/opt/ids2", image_name: str = "ids2:latest") -> bool:
        """Deploy Dockerfile and build image."""
        try:
            with self.ssh:
                logger.info(f"Deploying Dockerfile to {remote_dir}")
                
                # Create remote directory
                self.ssh.execute(f"mkdir -p {remote_dir}", sudo=True)
                
                # Upload Dockerfile
                dockerfile_name = Path(local_dockerfile).name
                remote_path = f"{remote_dir}/{dockerfile_name}"
                
                if not self.ssh.upload_file(local_dockerfile, remote_path):
                    return False
                
                # Build Docker image
                logger.info(f"Building Docker image: {image_name}")
                self.ssh.execute(
                    f"cd {remote_dir} && docker build -t {image_name} -f {dockerfile_name} .",
                    sudo=True
                )
                
                logger.info("Deployment completed successfully")
                return True
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            return False

    def deploy_directory(self, local_dir: str, remote_dir: str = "/opt/ids2") -> bool:
        """Deploy entire directory."""
        try:
            with self.ssh:
                logger.info(f"Deploying {local_dir} to {remote_dir}")
                return self.ssh.upload_directory(Path(local_dir), remote_dir)
        except Exception as e:
            logger.error(f"Directory deployment failed: {e}")
            return False

    def run_docker_container(self, image_name: str, container_name: str, ports: dict = None, volumes: dict = None) -> bool:
        """Run Docker container."""
        try:
            with self.ssh:
                # Stop existing container
                self.ssh.execute(f"docker stop {container_name} || true", sudo=True, check=False)
                self.ssh.execute(f"docker rm {container_name} || true", sudo=True, check=False)
                
                # Build docker run command
                cmd = f"docker run -d --name {container_name}"
                
                if ports:
                    for host_port, container_port in ports.items():
                        cmd += f" -p {host_port}:{container_port}"
                
                if volumes:
                    for host_vol, container_vol in volumes.items():
                        cmd += f" -v {host_vol}:{container_vol}"
                
                cmd += f" {image_name}"
                
                logger.info(f"Starting container: {container_name}")
                self.ssh.execute(cmd, sudo=True)
                
                return True
        except Exception as e:
            logger.error(f"Container start failed: {e}")
            return False
