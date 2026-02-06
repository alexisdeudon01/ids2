#!/usr/bin/env python3
"""Test SSH connectivity to Raspberry Pi."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "webbapp"))

from ids.deploy.config import DeployConfig
from ids.deploy.ssh_client import SSHClient

def main():
    config = DeployConfig(elastic_password="test")
    
    print(f"🔌 Testing SSH connection to {config.pi_ip} ({config.pi_host})...")
    print(f"   User: {config.pi_user}")
    print(f"   Key: {config.ssh_key_path}")
    
    try:
        with SSHClient(
            host=config.pi_ip,
            user=config.pi_user,
            password=config.pi_password,
            sudo_password=config.sudo_password,
            log_callback=print,
            ssh_key_path=config.ssh_key_path,
        ) as ssh:
            print("✅ SSH connection successful!")
            ssh.run("uname -a")
            ssh.run("hostname")
            ssh.run("uptime")
    except Exception as e:
        print(f"❌ SSH connection failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
