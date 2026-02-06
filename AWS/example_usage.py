#!/usr/bin/env python3
"""Example usage of refactored services."""

import logging
from app.ssh_manager import SSHManager
from app.pi_deployment import PiDeploymentService
from app.mysql_service import MySQLService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def example_ssh_deployment():
    """Example: Deploy to Pi via SSH."""
    ssh = SSHManager(
        host="192.168.1.100",
        user="pi",
        key_path="/home/user/.ssh/id_rsa"
    )
    
    deployer = PiDeploymentService(ssh)
    
    # Deploy Dockerfile
    deployer.deploy_dockerfile("./Dockerfile", "/opt/ids2")
    
    # Deploy entire directory
    deployer.deploy_directory("./app", "/opt/ids2/app")


def example_mysql_queries():
    """Example: MySQL queries."""
    with MySQLService(
        host="localhost",
        user="root",
        password="password",
        database="ids_db"
    ) as db:
        # SELECT query
        results = db.execute_query("SELECT * FROM alerts WHERE severity = %s", (1,))
        logger.info(f"Found {len(results)} critical alerts")
        
        # INSERT query
        db.execute_update(
            "INSERT INTO alerts (timestamp, severity, signature) VALUES (%s, %s, %s)",
            ("2024-01-01 12:00:00", 1, "Test Alert")
        )


if __name__ == "__main__":
    logger.info("Example usage - modify configuration before running")
