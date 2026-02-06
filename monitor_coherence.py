#!/usr/bin/env python3
"""Monitor infrastructure coherence (AWS, Pi, ELK)."""

import sys
import time
import socket
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / "webbapp"))

from ids.deploy.config import DeployConfig
from ids.deploy.ssh_client import SSHClient
from ids.deploy.aws_deployer import AWSDeployer

class CoherenceMonitor:
    """Monitor infrastructure coherence."""
    
    def __init__(self):
        self.config = DeployConfig(elastic_password="changeme")
        self.check_count = 0
        
    def check_ssh(self, host: str, port: int = 22, timeout: int = 3) -> bool:
        """Check SSH connectivity."""
        if not host:
            return False
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False
    
    def check_pi_service(self, service: str) -> dict:
        """Check service status on Pi."""
        try:
            with SSHClient(
                host=self.config.pi_ip,
                user=self.config.pi_user,
                password=self.config.pi_password,
                sudo_password=self.config.sudo_password,
                log_callback=lambda x: None,
                ssh_key_path=self.config.ssh_key_path,
            ) as ssh:
                exit_code, stdout, _ = ssh._exec(f"systemctl is-active {service}")
                status = stdout.strip()
                return {"status": status, "active": exit_code == 0}
        except Exception as e:
            return {"status": "error", "error": str(e), "active": False}
    
    def get_aws_instances(self) -> list:
        """Get AWS EC2 instances."""
        try:
            deployer = AWSDeployer(
                region=self.config.aws_region,
                elastic_password=self.config.elastic_password,
                log_callback=lambda x: None,
                aws_access_key_id=self.config.aws_access_key_id or None,
                aws_secret_access_key=self.config.aws_secret_access_key or None,
            )
            return deployer._find_existing_instances()
        except Exception:
            return []
    
    def run_check(self) -> None:
        """Run coherence check."""
        self.check_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"\n{'='*60}")
        print(f"🔍 Check #{self.check_count} - {timestamp}")
        print(f"{'='*60}")
        
        # Pi SSH
        pi_ssh = self.check_ssh(self.config.pi_ip)
        print(f"🔌 Pi SSH ({self.config.pi_ip}): {'✅' if pi_ssh else '❌'}")
        
        # Pi Services
        if pi_ssh:
            suricata = self.check_pi_service("suricata")
            webapp = self.check_pi_service("webbapp")
            
            print(f"🛡️  Suricata: {'✅ ' + suricata['status'] if suricata.get('active') else '❌ ' + suricata.get('status', 'unknown')}")
            print(f"🌐 Webapp: {'✅ ' + webapp['status'] if webapp.get('active') else '❌ ' + webapp.get('status', 'unknown')}")
        
        # AWS Instances
        instances = self.get_aws_instances()
        print(f"\n☁️  AWS Instances: {len(instances)}")
        
        for inst in instances:
            state = inst.state['Name']
            ip = inst.public_ip_address or "N/A"
            ssh_ok = self.check_ssh(inst.public_ip_address) if inst.public_ip_address else False
            print(f"   {inst.id}: {state} ({ip}) - SSH: {'✅' if ssh_ok else '❌'}")
    
    def run_forever(self, interval: int = 10) -> None:
        """Run continuous monitoring."""
        print("🚀 Starting Coherence Monitor")
        print(f"📊 Interval: {interval}s")
        print(f"📍 Pi: {self.config.pi_ip}")
        print(f"🌍 AWS: {self.config.aws_region}\n")
        
        try:
            while True:
                try:
                    self.run_check()
                except Exception as e:
                    print(f"❌ Check failed: {e}")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\n🛑 Stopped")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor IDS infrastructure")
    parser.add_argument("--interval", type=int, default=10, help="Check interval (default: 10s)")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    
    args = parser.parse_args()
    
    monitor = CoherenceMonitor()
    
    if args.once:
        monitor.run_check()
    else:
        monitor.run_forever(interval=args.interval)

if __name__ == "__main__":
    main()
