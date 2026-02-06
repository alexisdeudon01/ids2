#!/usr/bin/env python3
"""Test EC2 instance creation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "webbapp"))

from ids.deploy.config import DeployConfig
from ids.deploy.aws_deployer import AWSDeployer

def main():
    elastic_password = input("Mot de passe Elasticsearch: ").strip() or "changeme"
    
    config = DeployConfig(elastic_password=elastic_password)
    
    print(f"🚀 Testing EC2 instance creation...")
    print(f"   Region: {config.aws_region}")
    print(f"   Instance Type: {config.aws_instance_type}")
    
    try:
        deployer = AWSDeployer(
            region=config.aws_region,
            elastic_password=elastic_password,
            log_callback=print,
            aws_access_key_id=config.aws_access_key_id or None,
            aws_secret_access_key=config.aws_secret_access_key or None,
        )
        
        print("\n📊 Deploying ELK stack on EC2...")
        elk_ip = deployer.deploy_elk_stack()
        
        print(f"\n✅ EC2 instance created successfully!")
        print(f"📍 IP: {elk_ip}")
        print(f"🌐 Elasticsearch: http://{elk_ip}:9200")
        print(f"📊 Kibana: http://{elk_ip}:5601")
        
    except Exception as e:
        print(f"❌ EC2 creation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
