#!/usr/bin/env python3
"""Deploy AWS Dockerfile to Raspberry Pi."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "webbapp"))

from ids.deploy.config import DeployConfig
from ids.deploy.ssh_client import SSHClient


def main():
    """Deploy Dockerfile to Pi."""
    dockerfile = Path(__file__).parent / "Dockerfile"
    if not dockerfile.exists():
        print(f"❌ Dockerfile not found: {dockerfile}")
        sys.exit(1)
    
    config = DeployConfig(elastic_password="changeme")
    
    with SSHClient(
        host=config.pi_ip,
        user=config.pi_user,
        password=config.pi_password,
        sudo_password=config.sudo_password,
        log_callback=print,
        ssh_key_path=config.ssh_key_path,
    ) as ssh:
        remote_path = f"{config.remote_dir}/Dockerfile"
        ssh.run(f"mkdir -p '{config.remote_dir}'", sudo=True)
        ssh.sftp.put(str(dockerfile), remote_path)
        print(f"✅ Deployed: {remote_path}")


if __name__ == "__main__":
    main()
