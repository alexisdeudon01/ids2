#!/usr/bin/env python3
"""Monitor AWS EC2 instances."""

import os
import socket

try:
    import boto3
except ImportError:
    print("❌ boto3 not installed")
    exit(1)

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
    region = os.getenv("AWS_REGION", "eu-west-1")
    
    print(f"☁️  AWS Monitor - Region: {region}\n")
    
    ec2 = boto3.resource("ec2", region_name=region)
    
    instances = []
    for inst in ec2.instances.all():
        tags = {tag["Key"]: tag["Value"] for tag in (inst.tags or [])}
        if tags.get("Project") == "ids2":
            instances.append(inst)
    
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
