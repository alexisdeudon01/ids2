import json
import boto3
import subprocess
from datetime import datetime

def get_root_info():
    try:
        # Récupération de l'identité et de l'alias
        iam = boto3.client('iam')
        alias = iam.list_account_aliases()['AccountAliases'][0]
        account_id = boto3.client('sts').get_caller_identity()['Account']
        return {"RootAlias": alias, "AccountID": account_id}
    except:
        return {"RootAlias": "Unknown", "AccountID": "Unknown"}

def enrich_resources():
    session = boto3.Session()
    regions = [r['RegionName'] for r in session.client('ec2').describe_regions()['Regions']]
    all_entities = []

    print(f"Scanning {len(regions)} regions...")
    
    for region in regions:
        client = session.client('resourcegroupstaggingapi', region_name=region)
        paginator = client.get_paginator('get_resources')
        
        for page in paginator.paginate():
            for res in page['ResourceTagMappingList']:
                arn = res['ResourceARN']
                service = arn.split(':')[2]
                
                entity = {
                    "ARN": arn,
                    "Service": service,
                    "Region": region,
                    "Tags": {t['Key']: t['Value'] for t in res.get('Tags', [])},
                    "EnrichedData": {}
                }

                # Enrichissement spécifique (Exemple EC2)
                if service == 'ec2' and 'instance/' in arn:
                    ec2 = session.client('ec2', region_name=region)
                    iid = arn.split('/')[-1]
                    try:
                        details = ec2.describe_instances(InstanceIds=[iid])['Reservations'][0]['Instances'][0]
                        entity["EnrichedData"] = {
                            "State": details['State']['Name'],
                            "Type": details['InstanceType'],
                            "PublicIP": details.get('PublicIpAddress', 'N/A'),
                            "LaunchTime": details['LaunchTime'].isoformat()
                        }
                    except: pass
                
                all_entities.append(entity)

    # Export des données
    data = {
        "Metadata": {
            "GeneratedAt": datetime.now().isoformat(),
            "Account": get_root_info()
        },
        "Entities": all_entities
    }
    
    with open('AWSInstances.json', 'w') as f:
        json.dump(data, f, indent=4)

def generate_schema():
    schema = {
        "$schema": "http://json-schema.org",
        "title": "AWS Resource Schema",
        "type": "object",
        "properties": {
            "Metadata": {"type": "object"},
            "Entities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["ARN", "Service", "Region"],
                    "properties": {
                        "ARN": {"type": "string"},
                        "Service": {"type": "string"},
                        "Region": {"type": "string"},
                        "EnrichedData": {"type": "object"}
                    }
                }
            }
        }
    }
    with open('AWSchema.json', 'w') as f:
        json.dump(schema, f, indent=4)

if __name__ == "__main__":
    enrich_resources()
    generate_schema()
    print("Fichiers AWSInstances.json et AWSchema.json générés.")
