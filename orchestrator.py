#!/usr/bin/env python3
"""IDS Deployment Orchestrator - GUI & CLI."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "webbapp"))

from ids.deploy.gui import main as gui_main
from ids.deploy import AWSDeployer, DeployConfig

def restart_elk():
    """Restart ELK instance (CLI mode)."""
    elastic_password = input("Mot de passe Elasticsearch: ").strip()
    if not elastic_password:
        print("❌ Mot de passe requis")
        return
    
    config = DeployConfig(elastic_password=elastic_password)
    deployer = AWSDeployer(
        region=config.aws_region,
        elastic_password=elastic_password,
        log_callback=print,
        aws_access_key_id=config.aws_access_key_id or None,
        aws_secret_access_key=config.aws_secret_access_key or None,
    )
    
    instances = deployer._find_existing_instances()
    if instances:
        print(f"🧹 Terminaison de {len(instances)} instance(s)...")
        for inst in instances:
            inst.terminate()
        for inst in instances:
            inst.wait_until_terminated()
    
    print("🚀 Création d'une nouvelle instance...")
    elk_ip = deployer.deploy_elk_stack()
    
    print(f"\n✅ Instance redémarrée!")
    print(f"📊 Elasticsearch: http://{elk_ip}:9200")
    print(f"🌐 Kibana: http://{elk_ip}:5601")
    print(f"👤 elastic / {elastic_password}")
    
    print("\n⏳ Configuration d'Elasticsearch...")
    deployer.configure_elasticsearch(elk_ip)
    print(f"✅ Accédez à Kibana: http://{elk_ip}:5601")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--restart-elk":
        restart_elk()
    else:
        gui_main()
