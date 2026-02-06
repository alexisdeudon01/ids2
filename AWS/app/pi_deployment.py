"""Pi Deployment Service using SSH."""

import logging
from pathlib import Path
from .ssh_manager import SSHManager

logger = logging.getLogger(__name__)


class PiDeploymentService:
    """Deploy Docker containers to Raspberry Pi."""

    def __init__(self, ssh_manager: SSHManager):
        self.ssh = ssh_manager

    def deploy_dockerfile(self, local_dockerfile: str, remote_dir: str = "/opt/ids2") -> bool:
        """Deploy Dockerfile to Pi and build image."""
        try:
            with self.ssh:
                # Create remote directory
                logger.info(f"Creating remote directory: {remote_dir}")
                self.ssh.execute(f"mkdir -p {remote_dir}", sudo=True, verbose=True)
                
                # Upload Dockerfile
                logger.info("Uploading Dockerfile...")
                dockerfile_name = Path(local_dockerfile).name
                remote_path = f"{remote_dir}/{dockerfile_name}"
                
                if not self.ssh.upload_file(local_dockerfile, remote_path, verbose=True):
                    return False
                
                # Build Docker image
                logger.info("Building Docker image...")
                exit_code, stdout, stderr = self.ssh.execute(
                    f"cd {remote_dir} && docker build -t ids2-aws:latest -f {dockerfile_name} .",
                    sudo=True,
                    verbose=True
                )
                
                return exit_code == 0
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            return False

    def deploy_directory(self, local_dir: str, remote_dir: str = "/opt/ids2") -> bool:
        """Deploy entire directory to Pi."""
        try:
            with self.ssh:
                logger.info(f"Deploying {local_dir} to {remote_dir}")
                return self.ssh.upload_directory(local_dir, remote_dir, verbose=True)
        except Exception as e:
            logger.error(f"Directory deployment failed: {e}")
            return False
