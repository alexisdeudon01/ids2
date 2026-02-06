#!/usr/bin/env python3
"""Monitor database coherence with AWS."""

import os

try:
    import boto3
except ImportError:
    print("❌ boto3 not installed")
    exit(1)

def main():
    region = os.getenv("AWS_REGION", "eu-west-1")
    
    print("💾 Database Coherence Monitor\n")
    print(f"☁️  Checking AWS instances in {region}...\n")
    
    ec2 = boto3.resource("ec2", region_name=region)
    
    instances = []
    for inst in ec2.instances.all():
        tags = {tag["Key"]: tag["Value"] for tag in (inst.tags or [])}
        if tags.get("Project") == "ids2":
            instances.append(inst)
    
    print(f"Found {len(instances)} AWS instance(s)\n")
    
    if instances:
        print("AWS Instances:")
        for inst in instances:
            print(f"  {inst.id}: {inst.state['Name']} - {inst.public_ip_address or 'N/A'}")
    else:
        print("⚠️  No IDS2 instances found in AWS")

if __name__ == "__main__":
    main()
