"""AWS ELK stack deployer."""

from __future__ import annotations

import time
import urllib.request
from datetime import datetime
from typing import Callable

import boto3
import requests
from elasticsearch import Elasticsearch


PRICE_TABLE = {
    "eu-west-1": {
        "t3.medium": 0.0416,
    },
    "us-east-1": {
        "t3.medium": 0.0416,
    },
}


def _tqdm(iterable, **kwargs):
    try:
        from tqdm import tqdm  # type: ignore
        return tqdm(iterable, **kwargs)
    except Exception:
        return iterable




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
            self._session = session
        else:
            self._session = boto3.Session(region_name=region)

        self.ec2 = self._session.resource("ec2")
        self.ssm = self._session.client("ssm")
        self._ec2_client = self._session.client("ec2")

    def deploy_elk_stack(self) -> str:
        """Deploy ELK stack on EC2, returns public IP."""
        instance = self.ensure_instance()
        return self.ensure_elk_ready(instance)

    def ensure_instance(self):
        """Ensure a suitable EC2 instance exists (create/reuse)."""
        self._log("☁️ Preparing EC2 instance...")
        existing = self._find_existing_instances()
        if existing:
            self._log(f"🔎 Found {len(existing)} existing ELK instance(s).")
            for instance in existing:
                state = (instance.state or {}).get("Name")
                self._log(f"   - {instance.id} ({state})")
            instance = existing[0]
            state = (instance.state or {}).get("Name")
            if state in {"running", "pending"}:
                self._log(f"✅ Reusing instance {instance.id}")
                return instance
            self._log("⚠️ Existing instance stopped/stopping. Terminating and recreating.")
            self._terminate_instances(existing)

        return self._create_instance()

    def ensure_elk_ready(self, instance, retries: int = 1) -> str:
        """Wait for ELK to be healthy, recreating once if necessary."""
        for attempt in range(retries + 1):
            ip = self._wait_for_instance(instance)
            self._log(f"🔍 Waiting for Elasticsearch on {ip} (attempt {attempt + 1})")
            if self._wait_for_elk(ip):
                return ip
            self._log("⚠️ ELK not healthy. Terminating and recreating instance.")
            self._terminate_instances([instance])
            instance = self._create_instance()

        raise RuntimeError("ELK deployment failed (health timeout).")

    def _create_instance(self):
        my_ip = urllib.request.urlopen("https://checkip.amazonaws.com").read().decode("utf-8").strip()
        sg_id = self._ensure_security_group(my_ip)

        compose = self._build_docker_compose()
        user_data = self._build_user_data(compose)

        ami_id = self._resolve_ami_id()
        self._log(f"📦 Using AMI: {ami_id}")
        instances = self.ec2.create_instances(
            ImageId=ami_id,
            InstanceType="t3.medium",
            MinCount=1,
            MaxCount=1,
            SecurityGroupIds=[sg_id],
            UserData=user_data,
            TagSpecifications=[
                {
                    "ResourceType": "instance",
                    "Tags": [
                        {"Key": "Project", "Value": "ids2"},
                        {"Key": "Role", "Value": "elk"},
                        {"Key": "Name", "Value": "ids2-elk"},
                    ],
                }
            ],
        )

        return instances[0]

    def configure_elasticsearch(self, ip: str) -> None:
        """Configure Elasticsearch mappings and retention."""
        self._log("📊 Configuring Elasticsearch mappings & retention...")
        if not self._wait_for_elk(ip, timeout=240):
            raise RuntimeError("Elasticsearch not ready for configuration.")

        es = Elasticsearch(f"http://{ip}:9200", basic_auth=("elastic", self.elastic_password))

        try:
            info = es.info()
            self._log(f"✅ Elasticsearch {info.get('version', {}).get('number', 'unknown')} ready.")
        except Exception as exc:
            self._log(f"⚠️ Could not fetch cluster info: {exc}")

        # ILM policy
        try:
            es.ilm.get_lifecycle(name="ids-retention")
            self._log("ℹ️ ILM policy already exists.")
        except Exception:
            try:
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
                self._log("✅ ILM policy created.")
            except Exception as exc:
                self._log(f"⚠️ Failed to create ILM policy: {exc}")

        # Index template
        try:
            es.indices.get_index_template(name="ids-template")
            self._log("ℹ️ Index template already exists.")
        except Exception:
            try:
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
                self._log("✅ Index template created.")
            except Exception as exc:
                self._log(f"⚠️ Failed to create index template: {exc}")

        # Kibana data view
        try:
            resp = requests.post(
                f"http://{ip}:5601/api/data_views/data_view",
                auth=("elastic", self.elastic_password),
                json={"data_view": {"title": "suricata-*", "name": "Suricata Full Specs", "timeFieldName": "@timestamp"}},
                headers={"kbn-xsrf": "true"},
                timeout=10,
            )
            if resp.status_code in {200, 201, 409}:
                self._log("✅ Kibana data view ready.")
            else:
                self._log(f"⚠️ Kibana data view response: {resp.status_code} {resp.text}")
        except requests.RequestException as exc:
            self._log(f"⚠️ Kibana data view request failed: {exc}")

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

    def list_tagged_instances_all_regions(self) -> list[dict[str, str | None]]:
        """List tagged ELK instances across all regions."""
        regions = self._ec2_client.describe_regions().get("Regions", [])
        region_names = [region["RegionName"] for region in regions]
        results: list[dict[str, str | None]] = []
        filters = [
            {"Name": "tag:Project", "Values": ["ids2"]},
            {"Name": "tag:Role", "Values": ["elk"]},
            {"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]},
        ]
        for region in region_names:
            client = self._session.client("ec2", region_name=region)
            try:
                response = client.describe_instances(Filters=filters)
            except Exception as exc:
                self._log(f"⚠️ Failed to list instances in {region}: {exc}")
                continue
            for reservation in response.get("Reservations", []):
                for inst in reservation.get("Instances", []):
                    results.append(
                        {
                            "region": region,
                            "id": inst.get("InstanceId"),
                            "state": inst.get("State", {}).get("Name"),
                            "public_ip": inst.get("PublicIpAddress"),
                            "private_ip": inst.get("PrivateIpAddress"),
                            "instance_type": inst.get("InstanceType"),
                            "launch_time": inst.get("LaunchTime"),
                        }
                    )
        return results

    def select_instance_to_keep(self, instances: list[dict[str, str | None]]):
        if not instances:
            return None
        state_rank = {"running": 0, "pending": 1, "stopping": 2, "stopped": 3}

        def sort_key(item):
            rank = state_rank.get(item.get("state"), 99)
            launch = item.get("launch_time")
            launch_ts = launch.timestamp() if launch else 0
            return (rank, -launch_ts)

        return sorted(instances, key=sort_key)[0]

    def terminate_instances_across_regions(self, instances: list[dict[str, str | None]], keep_id: str | None = None) -> None:
        for inst in instances:
            instance_id = inst.get("id")
            region = inst.get("region")
            if not instance_id or not region:
                continue
            if keep_id and instance_id == keep_id:
                continue
            try:
                self._log(f"🧹 Terminating {instance_id} in {region}...")
                client = self._session.client("ec2", region_name=region)
                client.terminate_instances(InstanceIds=[instance_id])
            except Exception as exc:
                self._log(f"⚠️ Failed to terminate {instance_id}: {exc}")

    def terminate_instance(self, instance) -> None:
        try:
            instance.terminate()
            instance.wait_until_terminated()
        except Exception as exc:
            self._log(f"⚠️ Failed to terminate instance {getattr(instance, 'id', '?')}: {exc}")

    def stop_elasticsearch(self, instance_id: str) -> bool:
        commands = [
            "cd /home/ubuntu/elk && docker-compose down || true",
            "docker rm -f elasticsearch kibana || true",
            "rm -rf /home/ubuntu/elk || true",
        ]
        try:
            self.ssm.send_command(
                InstanceIds=[instance_id],
                DocumentName="AWS-RunShellScript",
                Parameters={"commands": commands},
            )
            self._log("✅ Stop Elasticsearch command sent via SSM.")
            return True
        except Exception as exc:
            self._log(f"⚠️ Failed to stop Elasticsearch via SSM: {exc}")
            return False

    def estimate_costs(self, instance_type: str | None, region: str | None = None) -> dict[str, float]:
        region = region or self.region
        instance_type = instance_type or "t3.medium"
        hourly_ec2 = PRICE_TABLE.get(region, {}).get(instance_type)
        if hourly_ec2 is None:
            hourly_ec2 = 0.0
            self._log(f"⚠️ Unknown pricing for {instance_type} in {region}.")
        hourly_elastic = 0.0
        monthly_ec2 = hourly_ec2 * 730
        monthly_elastic = hourly_elastic * 730
        return {
            "ec2_hourly_usd": hourly_ec2,
            "ec2_monthly_usd": monthly_ec2,
            "elastic_hourly_usd": hourly_elastic,
            "elastic_monthly_usd": monthly_elastic,
            "total_hourly_usd": hourly_ec2 + hourly_elastic,
            "total_monthly_usd": monthly_ec2 + monthly_elastic,
        }

    def _sleep_with_progress(self, seconds: int, label: str) -> None:
        for _ in _tqdm(range(seconds), desc=label, unit="s"):
            time.sleep(1)

    def _find_existing_instances(self) -> list:
        filters = [
            {"Name": "tag:Project", "Values": ["ids2"]},
            {"Name": "tag:Role", "Values": ["elk"]},
            {"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]},
        ]
        instances = list(self.ec2.instances.filter(Filters=filters))  # type: ignore[arg-type]
        return sorted(instances, key=lambda inst: getattr(inst, "launch_time", datetime.min), reverse=True)

    def _reuse_or_recreate(self, instances: list) -> str | None:
        instance = instances[0]
        state = (instance.state or {}).get("Name")
        if state in {"running", "pending"}:
            ip = self._wait_for_instance(instance)
            if self._wait_for_elk(ip):
                self._log(f"✅ Reusing existing ELK instance: {instance.id}")
                return ip
            self._log("⚠️ Existing instance not healthy. Terminating.")
            self._terminate_instances(instances)
            return None

        self._log("⚠️ Existing instance stopped/stopping. Terminating and recreating.")
        self._terminate_instances(instances)
        return None

    def _terminate_instances(self, instances: list) -> None:
        for instance in instances:
            try:
                self._log(f"🧹 Terminating instance {instance.id}...")
                instance.terminate()
            except Exception as exc:
                self._log(f"⚠️ Failed to terminate {instance.id}: {exc}")
        for instance in instances:
            try:
                instance.wait_until_terminated()
            except Exception:
                continue

    def _ensure_security_group(self, my_ip: str) -> str:
        groups = self._ec2_client.describe_security_groups(
            Filters=[{"Name": "group-name", "Values": ["ids2-elk-sg"]}]
        ).get("SecurityGroups", [])
        if groups:
            sg_id = groups[0]["GroupId"]
            self._log(f"✅ Reusing security group {sg_id}")
        else:
            sg = self.ec2.create_security_group(
                GroupName="ids2-elk-sg",
                Description="IDS2 ELK Access",
            )
            sg_id = sg.id
            self._log(f"✅ Created security group {sg_id}")

        try:
            self._ec2_client.authorize_security_group_ingress(
                GroupId=sg_id,
                IpPermissions=[
                    {"IpProtocol": "tcp", "FromPort": 9200, "ToPort": 9200, "IpRanges": [{"CidrIp": f"{my_ip}/32"}]},
                    {"IpProtocol": "tcp", "FromPort": 5601, "ToPort": 5601, "IpRanges": [{"CidrIp": f"{my_ip}/32"}]},
                ],
            )
        except Exception:
            pass
        return sg_id

    def _wait_for_instance(self, instance, timeout: int = 600) -> str:
        for _ in _tqdm(range(timeout), desc="Waiting for EC2 instance", unit="s"):
            instance.reload()
            state = (instance.state or {}).get("Name")
            if state == "running" and instance.public_ip_address:
                return instance.public_ip_address
            time.sleep(1)
        raise TimeoutError("EC2 instance did not become ready in time.")

    def _wait_for_elk(self, ip: str, timeout: int = 600) -> bool:
        for _ in _tqdm(range(timeout), desc="Waiting for ELK health", unit="s"):
            if self._probe_elk(ip):
                return True
            time.sleep(1)
        return False

    def _probe_elk(self, ip: str) -> bool:
        try:
            resp = requests.get(f"http://{ip}:9200", timeout=5)
            if resp.status_code in {200, 401}:
                return True
        except requests.RequestException:
            return False
        return False

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
