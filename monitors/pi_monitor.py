#!/usr/bin/env python3
"""Monitor Raspberry Pi services."""

import sys
import socket
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "webbapp"))

from ids.deploy.config import DeployConfig
from ids.deploy.ssh_client import SSHClient

def check_ssh(host: str, timeout: int = 3) -> bool:
    """Check SSH connectivity."""
    try:
        with socket.create_connection((host, 22), timeout=timeout):
            return True
    except OSError:
        return False

def check_service(config: DeployConfig, service: str) -> dict:
    """Check service status."""
    try:
        with SSHClient(
            host=config.pi_ip,
            user=config.pi_user,
            password=config.pi_password,
            sudo_password=config.sudo_password,
            log_callback=lambda x: None,
            ssh_key_path=config.ssh_key_path,
        ) as ssh:
            exit_code, stdout, _ = ssh._exec(f"systemctl is-active {service}")
            status = stdout.strip()
            return {"status": status, "active": exit_code == 0}
    except Exception as e:
        return {"status": "error", "error": str(e), "active": False}

def main():
    config = DeployConfig(elastic_password="changeme")
    
    print(f"🔌 Pi Monitor - {config.pi_ip} ({config.pi_host})\n")
    
    # SSH
    ssh_ok = check_ssh(config.pi_ip)
    print(f"SSH: {'✅' if ssh_ok else '❌'}")
    
    if not ssh_ok:
        print("❌ Cannot connect to Pi")
        sys.exit(1)
    
    # Services
    services = ["suricata", "webbapp", "ids"]
    
    print("\nServices:")
    for svc in services:
        result = check_service(config, svc)
        status = result['status']
        icon = '✅' if result.get('active') else '❌'
        print(f"  {svc}: {icon} {status}")

if __name__ == "__main__":
    main()
