"""AWS ELK stack deployer."""

from __future__ import annotations

import time
import urllib.request
from typing import Callable

import boto3
import requests
from elasticsearch import Elasticsearch


class AWSDeployer:
    """Deploy and configure ELK stack on AWS EC2."""
    
    def __init__(self, region: str, elastic_password: str, log_callback: Callable[[str], None]) -> None:
        self.region = region
        self.elastic_password = elastic_password
        self._log = log_callback
        self.ec2 = boto3.resource("ec2", region_name=region)

    def deploy_elk_stack(self) -> str:
        """Deploy ELK stack on EC2, returns public IP."""
        self._log("☁️ Deploying EC2 + ELK stack...")
        
        my_ip = urllib.request.urlopen("https://checkip.amazonaws.com").read().decode("utf-8").strip()
        
        sg = self.ec2.create_security_group(
            GroupName=f"ids-sg-{int(time.time())}",
            Description="IDS Access",
        )
        sg.authorize_ingress(IpProtocol="tcp", FromPort=9200, ToPort=9200, CidrIp=f"{my_ip}/32")
        sg.authorize_ingress(IpProtocol="tcp", FromPort=5601, ToPort=5601, CidrIp=f"{my_ip}/32")

        compose = self._build_docker_compose()
        user_data = self._build_user_data(compose)

        instances = self.ec2.create_instances(
            ImageId="ami-00c71bd4d220aa22a",
            InstanceType="t3.medium",
            MinCount=1,
            MaxCount=1,
            SecurityGroupIds=[sg.id],
            UserData=user_data,
        )
        
        instance = instances[0]
        instance.wait_until_running()
        instance.reload()
        return instance.public_ip_address

    def configure_elasticsearch(self, ip: str) -> None:
        """Configure Elasticsearch mappings and retention."""
        self._log("📊 Configuring Elasticsearch mappings & retention...")
        time.sleep(180)
        
        es = Elasticsearch(f"http://{ip}:9200", basic_auth=("elastic", self.elastic_password))
        
        es.ilm.put_lifecycle(
            name="ids-retention",
            body={
                "policy": {
                    "phases": {
                        "hot": {"actions": {"rollover": {"max_age": "1d"}}},
                        "delete": {"min_age": "7d", "actions": {"delete": {}}},
                    }
                }
            },
        )
        
        es.indices.put_index_template(
            name="ids-template",
            body={
                "index_patterns": ["suricata-*"],
                "template": {
                    "settings": {"index.lifecycle.name": "ids-retention"},
                    "mappings": {
                        "properties": {
                            "@timestamp": {"type": "date"},
                            "src_ip": {"type": "ip"},
                            "dest_ip": {"type": "ip"},
                            "src_port": {"type": "integer"},
                            "dest_port": {"type": "integer"},
                            "proto": {"type": "keyword"},
                            "event_type": {"type": "keyword"},
                            "flow.total_bytes": {"type": "long"},
                            "alert.severity": {"type": "integer"},
                            "alert.signature": {"type": "keyword"},
                        }
                    },
                },
            },
        )
        
        requests.post(
            f"http://{ip}:5601/api/data_views/data_view",
            auth=("elastic", self.elastic_password),
            json={"data_view": {"title": "suricata-*", "name": "Suricata Full Specs", "timeFieldName": "@timestamp"}},
            headers={"kbn-xsrf": "true"},
            timeout=10,
        )

    def _build_docker_compose(self) -> str:
        return (
            "version: '3.8'\n"
            "services:\n"
            "  elasticsearch:\n"
            "    image: docker.elastic.co/elasticsearch/elasticsearch:8.12.0\n"
            "    environment: [discovery.type=single-node, xpack.security.enabled=true, "
            f"ELASTIC_PASSWORD={self.elastic_password}, 'ES_JAVA_OPTS=-Xms2g -Xmx2g']\n"
            "    ports: ['9200:9200']\n"
            "  kibana:\n"
            "    image: docker.elastic.co/kibana/kibana:8.12.0\n"
            "    ports: ['5601:5601']\n"
            "    depends_on: [elasticsearch]\n"
            "    environment: [ELASTICSEARCH_HOSTS=http://elasticsearch:9200, "
            f"ELASTICSEARCH_USERNAME=elastic, ELASTICSEARCH_PASSWORD={self.elastic_password}]"
        )

    def _build_user_data(self, compose: str) -> str:
        return (
            "#!/bin/bash\n"
            "apt update && apt install -y docker.io docker-compose\n"
            "sysctl -w vm.max_map_count=262144\n"
            "mkdir -p /home/ubuntu/elk && echo \""
            + compose.replace('"', '\\"')
            + "\" > /home/ubuntu/elk/docker-compose.yml\n"
            "cd /home/ubuntu/elk && docker-compose up -d"
        )
