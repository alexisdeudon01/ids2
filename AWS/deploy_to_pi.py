#!/usr/bin/env python3
"""Deploy AWS Dockerfile to Raspberry Pi."""

import logging
import sys
from pathlib import Path
from app.ssh_manager import SSHManager
from app.pi_deployment import PiDeploymentService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Main deployment function."""
    # Configuration
    PI_HOST = "192.168.1.100"  # Change to your Pi IP
    PI_USER = "pi"
    PI_KEY = str(Path.home() / ".ssh" / "id_rsa")
    
    # Dockerfile path
    dockerfile_path = Path(__file__).parent / "Dockerfile"
    
    if not dockerfile_path.exists():
        logger.error(f"Dockerfile not found: {dockerfile_path}")
        sys.exit(1)
    
    logger.info("Starting deployment to Raspberry Pi...")
    
    # Create SSH manager
    ssh = SSHManager(PI_HOST, PI_USER, PI_KEY)
    
    # Create deployment service
    deployer = PiDeploymentService(ssh)
    
    # Deploy Dockerfile
    success = deployer.deploy_dockerfile(str(dockerfile_path))
    
    if success:
        logger.info("Deployment completed successfully!")
        sys.exit(0)
    else:
        logger.error("Deployment failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
