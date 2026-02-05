"""AWS + Suricata orchestration (based on provided script)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from typing import Callable

import boto3
import requests
from elasticsearch import Elasticsearch, helpers


class SuricataMaster:
    """Deploy ELK on AWS and stream Suricata logs."""

    def __init__(self, region: str, es_pwd: str, log: Callable[[str], None] | None = None) -> None:
        self.region = region
        self.es_pwd = es_pwd
        self.log_path = "/var/log/suricata/eve.json"
        self.ec2 = boto3.resource("ec2", region_name=region)
        self._log = log or (lambda msg: print(msg, flush=True))

    def deploy_aws(self) -> str:
        self._log("☁️ Déploiement EC2 + ELK (Full Metadata)...")
        my_ip = (
            urllib.request.urlopen("https://checkip.amazonaws.com")
            .read()
            .decode("utf-8")
            .strip()
        )
        sg = self.ec2.create_security_group(
            GroupName=f"ids-sg-{int(time.time())}",
            Description="IDS Access",
        )
        sg.authorize_ingress(IpProtocol="tcp", FromPort=9200, ToPort=9200, CidrIp=f"{my_ip}/32")
        sg.authorize_ingress(IpProtocol="tcp", FromPort=5601, ToPort=5601, CidrIp=f"{my_ip}/32")

        compose = (
            "version: '3.8'\n"
            "services:\n"
            "  elasticsearch:\n"
            "    image: docker.elastic.co/elasticsearch/elasticsearch:8.12.0\n"
            "    environment: [discovery.type=single-node, xpack.security.enabled=true, "
            f"ELASTIC_PASSWORD={self.es_pwd}, 'ES_JAVA_OPTS=-Xms2g -Xmx2g']\n"
            "    ports: ['9200:9200']\n"
            "  kibana:\n"
            "    image: docker.elastic.co/kibana/kibana:8.12.0\n"
            "    ports: ['5601:5601']\n"
            "    depends_on: [elasticsearch]\n"
            "    environment: [ELASTICSEARCH_HOSTS=http://elasticsearch:9200, "
            f"ELASTICSEARCH_USERNAME=elastic, ELASTICSEARCH_PASSWORD={self.es_pwd}]"
        )

        user_data = (
            "#!/bin/bash\n"
            "apt update && apt install -y docker.io docker-compose\n"
            "sysctl -w vm.max_map_count=262144\n"
            "mkdir -p /home/ubuntu/elk && echo \""
            + compose.replace('"', '\\"')
            + "\" > /home/ubuntu/elk/docker-compose.yml\n"
            "cd /home/ubuntu/elk && docker-compose up -d"
        )

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

    def configure_es_mapping(self, ip: str) -> None:
        self._log("📊 Configuration Mapping (IP/Flow/Alert) & Rétention...")
        time.sleep(180)
        es = Elasticsearch(f"http://{ip}:9200", basic_auth=("elastic", self.es_pwd))

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
                "index_patterns": ["suricata-*"] ,
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
            auth=("elastic", self.es_pwd),
            json={"data_view": {"title": "suricata-*", "name": "Suricata Full Specs", "timeFieldName": "@timestamp"}},
            headers={"kbn-xsrf": "true"},
            timeout=10,
        )

    def start_stream(self, ip: str, pwd: str) -> None:
        es = Elasticsearch(f"http://{ip}:9200", basic_auth=("elastic", pwd))
        self._log(f"🚀 Flux Meta-Data actif vers {ip}")
        while True:
            if os.path.exists(self.log_path) and os.path.getsize(self.log_path) > 0:
                try:
                    with open(self.log_path, "r+", encoding="utf-8") as handle:
                        lines = handle.readlines()
                        if lines:
                            actions = []
                            for line in lines:
                                data = json.loads(line)
                                if "timestamp" in data:
                                    data["@timestamp"] = data.pop("timestamp")
                                data.pop("payload", None)
                                data.pop("payload_printable", None)
                                if "flow" in data:
                                    data["flow"]["total_bytes"] = data["flow"].get("bytes_toclient", 0) + data["flow"].get(
                                        "bytes_toserver", 0
                                    )
                                actions.append(
                                    {
                                        "_index": f"suricata-{time.strftime('%Y.%m.%d')}",
                                        "_source": data,
                                    }
                                )
                            helpers.bulk(es, actions)
                            handle.seek(0)
                            handle.truncate()
                except Exception:
                    pass
            time.sleep(1)

    @staticmethod
    def build_systemd_service(service_path: str, ip: str, pwd: str) -> str:
        return (
            "[Unit]\n"
            "Description=IDS-Full-Meta-Streamer\n"
            "After=suricata.service\n"
            "\n"
            "[Service]\n"
            f"ExecStart=/usr/bin/python3 {service_path} {ip} {pwd}\n"
            "Restart=always\n"
            "User=root\n"
            "\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n"
        )


if __name__ == "__main__":
    if len(sys.argv) > 2:
        SuricataMaster("", "").start_stream(sys.argv[1], sys.argv[2])
    else:
        region = input("Région AWS : ")
        pwd = input("Pass Elastic : ")
        master = SuricataMaster(region, pwd)
        ip_addr = master.deploy_aws()
        master.configure_es_mapping(ip_addr)
        service_text = SuricataMaster.build_systemd_service(os.path.abspath(__file__), ip_addr, pwd)
        with open("/tmp/ids.service", "w", encoding="utf-8") as handle:
            handle.write(service_text)
        subprocess.run(["sudo", "mv", "/tmp/ids.service", "/etc/systemd/system/ids.service"], check=False)
        subprocess.run(["sudo", "systemctl", "daemon-reload"], check=False)
        subprocess.run(["sudo", "systemctl", "enable", "--now", "ids"], check=False)
        print(f"🔥 Dashboard prêt (Sans Payloads) : http://{ip_addr}:5601")
