#!/usr/bin/env python3
"""Monitor database coherence with real-world state (AWS, Pi, EC2)."""

import json
import sys
import time
import socket
from pathlib import Path
from datetime import datetime
from typing import Any

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "webbapp"))

try:
    import pymysql
except ImportError:
    print("❌ pymysql not installed. Install with: pip3 install pymysql")
    sys.exit(1)

try:
    import boto3
except ImportError:
    print("⚠️  boto3 not installed. AWS checks will be skipped.")
    boto3 = None

try:
    import paramiko
except ImportError:
    print("⚠️  paramiko not installed. SSH checks will be skipped.")
    paramiko = None


class CoherenceMonitor:
    """Monitor DB coherence with real world."""
    
    def __init__(self, config_path: str = "../config.json"):
        self.config = self._load_config(config_path)
        self.db_conn = None
        self.check_count = 0
        
    def _load_config(self, path: str) -> dict[str, Any]:
        """Load configuration from JSON file."""
        config_file = Path(__file__).parent / path
        if not config_file.exists():
            print(f"❌ Config not found: {config_file}")
            sys.exit(1)
        return json.loads(config_file.read_text())
    
    def connect_db(self) -> None:
        """Connect to MySQL on Pi."""
        pi_ip = self.config.get("pi_ip", "192.168.178.66")
        
        try:
            self.db_conn = pymysql.connect(
                host=pi_ip,
                port=3306,
                user="ids_user",
                password="admin",
                database="ids_db",
                connect_timeout=5,
            )
            print(f"✅ Connected to MySQL on Pi ({pi_ip})")
        except Exception as e:
            print(f"❌ Cannot connect to MySQL: {e}")
            sys.exit(1)
    
    def check_db_health(self) -> bool:
        """Check if database is accessible."""
        try:
            with self.db_conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                return True
        except Exception:
            return False
    
    def get_db_instances(self) -> list[dict]:
        """Get EC2 instances from database."""
        try:
            with self.db_conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute("""
                    SELECT instance_id, region, instance_type, public_ip, 
                           private_ip, state, elk_deployed, updated_at
                    FROM ec2_instances
                    ORDER BY updated_at DESC
                """)
                return cursor.fetchall()
        except Exception as e:
            print(f"⚠️  DB query failed: {e}")
            return []
    
    def get_aws_instances(self) -> list[dict]:
        """Get actual EC2 instances from AWS."""
        if not boto3:
            return []
        
        instances = []
        try:
            regions = self.config.get("aws_region", "eu-west-1").split(",")
            
            for region in regions:
                session = boto3.Session(
                    aws_access_key_id=self.config.get("aws_access_key_id") or None,
                    aws_secret_access_key=self.config.get("aws_secret_access_key") or None,
                    region_name=region.strip(),
                )
                ec2 = session.resource("ec2")
                
                for instance in ec2.instances.all():
                    # Check if it's an IDS2 instance
                    tags = {tag["Key"]: tag["Value"] for tag in (instance.tags or [])}
                    if tags.get("Project") == "ids2":
                        instances.append({
                            "instance_id": instance.id,
                            "region": region.strip(),
                            "instance_type": instance.instance_type,
                            "public_ip": instance.public_ip_address or "",
                            "private_ip": instance.private_ip_address or "",
                            "state": (instance.state or {}).get("Name", ""),
                        })
        except Exception as e:
            print(f"⚠️  AWS query failed: {e}")
        
        return instances
    
    def check_ssh_connectivity(self, host: str, port: int = 22, timeout: int = 3) -> bool:
        """Check if SSH port is reachable."""
        if not host:
            return False
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False
    
    def check_service_on_pi(self, service_name: str) -> dict:
        """Check if a service is running on Pi via SSH."""
        if not paramiko:
            return {"status": "unknown", "error": "paramiko not installed"}
        
        pi_target = self.config.get("pi_ip") or self.config.get("pi_host", "sinik")
        pi_user = self.config.get("pi_user", "pi")
        ssh_key = self.config.get("ssh_key_path", "/home/tor/.ssh/pi_key")
        
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                hostname=pi_target,
                username=pi_user,
                key_filename=ssh_key,
                timeout=5,
            )
            
            stdin, stdout, stderr = client.exec_command(f"systemctl is-active {service_name}")
            status = stdout.read().decode().strip()
            
            client.close()
            
            return {
                "status": status,
                "active": status == "active",
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "active": False}
    
    def reconcile_instances(self) -> dict:
        """Compare DB instances with AWS reality."""
        db_instances = {inst["instance_id"]: inst for inst in self.get_db_instances()}
        aws_instances = {inst["instance_id"]: inst for inst in self.get_aws_instances()}
        
        # Instances in DB but not in AWS (deleted?)
        orphan_db = set(db_instances.keys()) - set(aws_instances.keys())
        
        # Instances in AWS but not in DB (new?)
        missing_db = set(aws_instances.keys()) - set(db_instances.keys())
        
        # Instances with mismatched state
        mismatched = []
        for inst_id in set(db_instances.keys()) & set(aws_instances.keys()):
            db_inst = db_instances[inst_id]
            aws_inst = aws_instances[inst_id]
            
            if db_inst["state"] != aws_inst["state"]:
                mismatched.append({
                    "instance_id": inst_id,
                    "db_state": db_inst["state"],
                    "aws_state": aws_inst["state"],
                })
            
            if db_inst["public_ip"] != aws_inst["public_ip"]:
                mismatched.append({
                    "instance_id": inst_id,
                    "db_ip": db_inst["public_ip"],
                    "aws_ip": aws_inst["public_ip"],
                })
        
        return {
            "db_instances": len(db_instances),
            "aws_instances": len(aws_instances),
            "orphan_in_db": list(orphan_db),
            "missing_in_db": list(missing_db),
            "mismatched": mismatched,
        }
    
    def update_db_from_aws(self) -> None:
        """Update database with current AWS state."""
        aws_instances = self.get_aws_instances()
        
        if not aws_instances:
            return
        
        try:
            with self.db_conn.cursor() as cursor:
                for inst in aws_instances:
                    cursor.execute("""
                        INSERT INTO ec2_instances 
                        (instance_id, region, instance_type, public_ip, private_ip, state, elk_deployed, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                        ON DUPLICATE KEY UPDATE
                            region=VALUES(region),
                            instance_type=VALUES(instance_type),
                            public_ip=VALUES(public_ip),
                            private_ip=VALUES(private_ip),
                            state=VALUES(state),
                            updated_at=NOW()
                    """, (
                        inst["instance_id"],
                        inst["region"],
                        inst["instance_type"],
                        inst["public_ip"],
                        inst["private_ip"],
                        inst["state"],
                        0,  # elk_deployed will be updated separately
                    ))
                self.db_conn.commit()
                print(f"✅ Updated {len(aws_instances)} instance(s) in DB")
        except Exception as e:
            print(f"⚠️  DB update failed: {e}")
    
    def delete_orphan_instances(self, orphan_ids: list[str]) -> None:
        """Remove instances from DB that no longer exist in AWS."""
        if not orphan_ids:
            return
        
        try:
            with self.db_conn.cursor() as cursor:
                placeholders = ",".join(["%s"] * len(orphan_ids))
                cursor.execute(
                    f"DELETE FROM ec2_instances WHERE instance_id IN ({placeholders})",
                    orphan_ids
                )
                self.db_conn.commit()
                print(f"🗑️  Deleted {len(orphan_ids)} orphan instance(s) from DB")
        except Exception as e:
            print(f"⚠️  Failed to delete orphans: {e}")
    
    def run_coherence_check(self) -> None:
        """Run a single coherence check."""
        self.check_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"\n{'='*60}")
        print(f"🔍 Coherence Check #{self.check_count} - {timestamp}")
        print(f"{'='*60}")
        
        # 1. DB Health
        db_ok = self.check_db_health()
        print(f"📊 Database: {'✅ OK' if db_ok else '❌ FAIL'}")
        
        if not db_ok:
            print("❌ Cannot proceed without DB access")
            return
        
        # 2. SSH Connectivity
        pi_target = self.config.get("pi_ip") or self.config.get("pi_host", "sinik")
        pi_ssh = self.check_ssh_connectivity(pi_target)
        print(f"🔌 Pi SSH ({pi_target}): {'✅ OK' if pi_ssh else '❌ FAIL'}")
        
        # 3. Services on Pi
        if pi_ssh:
            suricata = self.check_service_on_pi("suricata")
            mysql = self.check_service_on_pi("mysql")
            webbapp = self.check_service_on_pi("webbapp")
            
            print(f"🛡️  Suricata: {'✅ ' + suricata['status'] if suricata.get('active') else '❌ ' + suricata.get('status', 'unknown')}")
            print(f"💾 MySQL: {'✅ ' + mysql['status'] if mysql.get('active') else '❌ ' + mysql.get('status', 'unknown')}")
            print(f"🌐 Webapp: {'✅ ' + webbapp['status'] if webbapp.get('active') else '❌ ' + webbapp.get('status', 'unknown')}")
        
        # 4. AWS vs DB Reconciliation
        if boto3:
            reconcile = self.reconcile_instances()
            
            print(f"\n🔄 Reconciliation:")
            print(f"   DB instances: {reconcile['db_instances']}")
            print(f"   AWS instances: {reconcile['aws_instances']}")
            
            if reconcile['orphan_in_db']:
                print(f"   ⚠️  Orphan in DB (not in AWS): {reconcile['orphan_in_db']}")
                # Auto-cleanup orphans
                self.delete_orphan_instances(reconcile['orphan_in_db'])
            
            if reconcile['missing_in_db']:
                print(f"   ⚠️  Missing in DB (exists in AWS): {reconcile['missing_in_db']}")
                # Auto-add missing instances
                self.update_db_from_aws()
            
            if reconcile['mismatched']:
                print(f"   ⚠️  Mismatched data: {len(reconcile['mismatched'])} instance(s)")
                for mm in reconcile['mismatched'][:3]:  # Show first 3
                    print(f"      - {mm}")
                # Auto-update mismatches
                self.update_db_from_aws()
            
            if not reconcile['orphan_in_db'] and not reconcile['missing_in_db'] and not reconcile['mismatched']:
                print("   ✅ DB and AWS are in sync")
        
        # 5. Check EC2 SSH connectivity
        db_instances = self.get_db_instances()
        for inst in db_instances:
            if inst["state"] == "running" and inst["public_ip"]:
                ec2_ssh = self.check_ssh_connectivity(inst["public_ip"])
                print(f"🔌 EC2 SSH ({inst['instance_id']}): {'✅ OK' if ec2_ssh else '❌ FAIL'}")
    
    def run_forever(self, interval: int = 10) -> None:
        """Run coherence checks continuously."""
        print("🚀 Starting DB Coherence Monitor")
        print(f"📊 Check interval: {interval} seconds")
        print(f"📍 Pi: {self.config.get('pi_ip', 'N/A')}")
        print(f"🌍 AWS Region: {self.config.get('aws_region', 'N/A')}")
        print("\nPress Ctrl+C to stop\n")
        
        try:
            while True:
                try:
                    self.run_coherence_check()
                except Exception as e:
                    print(f"❌ Check failed: {e}")
                
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\n🛑 Monitor stopped by user")
            if self.db_conn:
                self.db_conn.close()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor IDS database coherence")
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Check interval in seconds (default: 10)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit (no continuous monitoring)",
    )
    parser.add_argument(
        "--config",
        default="../config.json",
        help="Path to config.json (default: ../config.json)",
    )
    
    args = parser.parse_args()
    
    monitor = CoherenceMonitor(config_path=args.config)
    monitor.connect_db()
    
    if args.once:
        monitor.run_coherence_check()
    else:
        monitor.run_forever(interval=args.interval)


if __name__ == "__main__":
    main()
