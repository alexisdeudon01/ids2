#!/usr/bin/env python3
"""Monitor database coherence with AWS."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "webbapp"))

from db.database import Database
from ids.deploy.config import DeployConfig
from ids.deploy.aws_deployer import AWSDeployer

def main():
    config = DeployConfig(elastic_password="changeme")
    db = Database("webbapp/db/ids.db")
    
    print("💾 Database Coherence Monitor\n")
    
    # Get DB config
    db_config = db.get_deployment_config()
    if db_config:
        print("Database config:")
        print(f"  Region: {db_config.get('aws_region', 'N/A')}")
        print(f"  ELK IP: {db_config.get('elk_ip', 'N/A')}")
        print(f"  Pi: {db_config.get('pi_host', 'N/A')}")
    else:
        print("⚠️  No deployment config in database")
    
    # Get AWS instances
    print("\n☁️  Checking AWS instances...")
    
    try:
        deployer = AWSDeployer(
            region=config.aws_region,
            elastic_password=config.elastic_password,
            log_callback=lambda x: None,
            aws_access_key_id=config.aws_access_key_id or None,
            aws_secret_access_key=config.aws_secret_access_key or None,
        )
        
        aws_instances = deployer._find_existing_instances()
        
        print(f"Found {len(aws_instances)} AWS instance(s)")
        
        # Compare with DB
        if db_config and db_config.get('elk_ip'):
            db_elk_ip = db_config['elk_ip']
            aws_ips = [inst.public_ip_address for inst in aws_instances if inst.public_ip_address]
            
            if db_elk_ip in aws_ips:
                print(f"✅ DB ELK IP ({db_elk_ip}) matches AWS")
            else:
                print(f"⚠️  DB ELK IP ({db_elk_ip}) not found in AWS")
                if aws_ips:
                    print(f"   AWS IPs: {', '.join(aws_ips)}")
                    print(f"\n🔄 Updating database with latest AWS IP...")
                    db.save_deployment_config(
                        aws_region=config.aws_region,
                        elk_ip=aws_ips[0],
                        elastic_password=config.elastic_password,
                        pi_host=config.pi_host,
                        pi_user=config.pi_user,
                        pi_password=config.pi_password,
                        sudo_password=config.sudo_password,
                        remote_dir=config.remote_dir,
                        mirror_interface=config.mirror_interface,
                    )
                    print(f"✅ Database updated with IP: {aws_ips[0]}")
        
        # Show AWS instances
        if aws_instances:
            print("\nAWS Instances:")
            for inst in aws_instances:
                print(f"  {inst.id}: {inst.state['Name']} - {inst.public_ip_address or 'N/A'}")
        
    except Exception as e:
        print(f"❌ AWS check failed: {e}")

if __name__ == "__main__":
    main()
