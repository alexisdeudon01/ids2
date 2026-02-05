"""AWS ELK stack deployer."""

from __future__ import annotations

import time
import urllib.request
from typing import Callable

import requests
import boto3
from elasticsearch import Elasticsearch




class AWSDeployer:
    """Deploy and configure ELK stack on AWS EC2."""
    
    def __init__(
        self,
        region: str,
        elastic_password: str,
        log_callback: Callable[[str], None],
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        ami_id: str | None = None,
    ) -> None:
        self.region = region
        self.elastic_password = elastic_password
        self._log = log_callback
        self.ami_id = (ami_id or "").strip()

        access_key = aws_access_key_id or None
        secret_key = aws_secret_access_key or None
        if access_key and secret_key:
            session = boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region,
            )
            self.ec2 = session.resource("ec2")
            self.ssm = session.client("ssm")
        else:
            self.ec2 = boto3.resource("ec2", region_name=region)
            self.ssm = boto3.client("ssm", region_name=region)

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

        ami_id = self._resolve_ami_id()
        instances = self.ec2.create_instances(
            ImageId=ami_id,
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

    def list_instances(self) -> list[dict[str, str | None]]:
        """List EC2 instances in the configured region."""
        instances = []
        for instance in self.ec2.instances.all():
            instances.append(
                {
                    "id": instance.id,
                    "state": instance.state.get("Name") if instance.state else None,
                    "public_ip": getattr(instance, "public_ip_address", None),
                    "private_ip": getattr(instance, "private_ip_address", None),
                }
            )
        return instances

    def _resolve_ami_id(self) -> str:
        if self.ami_id:
            return self.ami_id

        candidates = [
            "/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp3/ami-id",
            "/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id",
        ]
        for param in candidates:
            try:
                response = self.ssm.get_parameter(Name=param)
                value = response.get("Parameter", {}).get("Value")
                if value:
                    self._log(f"✅ AMI resolved from SSM: {value}")
                    return value
            except Exception:
                continue

        raise RuntimeError(
            "AMI introuvable pour cette région. "
            "Renseignez aws_ami_id dans config.json ou dans l'UI."
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
