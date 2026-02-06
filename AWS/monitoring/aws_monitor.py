#!/usr/bin/env python3
"""Monitor AWS EC2 instances."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "webbapp"))

from ids.deploy.config import DeployConfig
from ids.deploy.aws_deployer import AWSDeployer
import socket

def check_ssh(host: str, timeout: int = 3) -> bool:
    """Check SSH connectivity."""
    if not host:
        return False
    try:
        with socket.create_connection((host, 22), timeout=timeout):
            return True
    except OSError:
        return False

def main():
    config = DeployConfig(elastic_password="changeme")
    
    print(f"☁️  AWS Monitor - Region: {config.aws_region}\n")
    
    deployer = AWSDeployer(
        region=config.aws_region,
        elastic_password=config.elastic_password,
        log_callback=lambda x: None,
        aws_access_key_id=config.aws_access_key_id or None,
        aws_secret_access_key=config.aws_secret_access_key or None,
    )
    
    instances = deployer._find_existing_instances()
    
    print(f"Found {len(instances)} IDS2 instance(s):\n")
    
    for inst in instances:
        state = inst.state['Name']
        ip = inst.public_ip_address or "N/A"
        ssh_ok = check_ssh(inst.public_ip_address) if inst.public_ip_address else False
        
        print(f"  {inst.id}")
        print(f"    State: {state}")
        print(f"    IP: {ip}")
        print(f"    SSH: {'✅' if ssh_ok else '❌'}")
        print()

if __name__ == "__main__":
    main()
