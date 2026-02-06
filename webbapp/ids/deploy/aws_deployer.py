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
        instance_type: str | None = None,
        key_name: str | None = None,
        subnet_id: str | None = None,
        vpc_id: str | None = None,
        security_group_id: str | None = None,
        iam_instance_profile: str | None = None,
        root_volume_gb: int | None = None,
        root_volume_type: str | None = None,
        associate_public_ip: bool | None = None,
    ) -> None:
        self.region = region
        self.elastic_password = elastic_password
        self._log = log_callback
        self.ami_id = (ami_id or "").strip()
        self.instance_type = (instance_type or "t3.medium").strip()
        self.key_name = (key_name or "").strip()
        self.subnet_id = (subnet_id or "").strip()
        self.vpc_id = (vpc_id or "").strip()
        self.security_group_id = (security_group_id or "").strip()
        self.iam_instance_profile = (iam_instance_profile or "").strip()
        self.root_volume_gb = int(root_volume_gb or 30)
        self.root_volume_type = (root_volume_type or "gp3").strip()
        self.associate_public_ip = True if associate_public_ip is None else bool(associate_public_ip)
        self._last_instance_id: str | None = None

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
                self._last_instance_id = instance.id
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

    def log_access_info(self, ip: str) -> None:
        self._log(f"🌐 Elasticsearch: http://{ip}:9200")
        self._log(f"🌐 Kibana: http://{ip}:5601")

    def verify_services(self, ip: str) -> bool:
        """Verify Elasticsearch and Kibana availability."""
        elk_ok = self._probe_elk(ip)
        kibana_ok = self._probe_kibana(ip)
        if elk_ok:
            self._log("✅ Elasticsearch responding.")
        else:
            self._log("❌ Elasticsearch not responding.")
        if kibana_ok:
            self._log("✅ Kibana responding.")
        else:
            self._log("❌ Kibana not responding.")

        if (not elk_ok or not kibana_ok) and self._last_instance_id:
            self._log("🧰 Checking Docker status via SSM...")
            self._log_docker_status(self._last_instance_id)
            if not kibana_ok:
                self._log("🔁 Attempting Kibana restart via docker-compose...")
                if self._redeploy_elk_via_ssm(self._last_instance_id):
                    kibana_ok = self._wait_for_kibana(ip, timeout=240)
        return elk_ok and kibana_ok

    def _create_instance(self):
        my_ip = urllib.request.urlopen("https://checkip.amazonaws.com").read().decode("utf-8").strip()
        sg_id = self.security_group_id or self._ensure_security_group(my_ip)

        compose = self._build_docker_compose()
        user_data = self._build_user_data(compose)

        ami_id = self._resolve_ami_id()
        self._log(f"📦 Using AMI: {ami_id}")
        self._log_instance_config(ami_id, sg_id)

        instance_params: dict[str, object] = {
            "ImageId": ami_id,
            "InstanceType": self.instance_type,
            "MinCount": 1,
            "MaxCount": 1,
            "UserData": user_data,
            "TagSpecifications": [
                {
                    "ResourceType": "instance",
                    "Tags": [
                        {"Key": "Project", "Value": "ids2"},
                        {"Key": "Role", "Value": "elk"},
                        {"Key": "Name", "Value": "ids2-elk"},
                    ],
                }
            ],
            "BlockDeviceMappings": [
                {
                    "DeviceName": "/dev/sda1",
                    "Ebs": {
                        "VolumeSize": self.root_volume_gb,
                        "VolumeType": self.root_volume_type,
                        "DeleteOnTermination": True,
                    },
                }
            ],
        }

        if self.key_name:
            instance_params["KeyName"] = self.key_name

        if self.iam_instance_profile:
            if self.iam_instance_profile.startswith("arn:"):
                instance_params["IamInstanceProfile"] = {"Arn": self.iam_instance_profile}
            else:
                instance_params["IamInstanceProfile"] = {"Name": self.iam_instance_profile}

        if self.subnet_id:
            instance_params["NetworkInterfaces"] = [
                {
                    "DeviceIndex": 0,
                    "SubnetId": self.subnet_id,
                    "Groups": [sg_id],
                    "AssociatePublicIpAddress": self.associate_public_ip,
                }
            ]
        else:
            instance_params["SecurityGroupIds"] = [sg_id]

        instances = self.ec2.create_instances(**instance_params)

        instance = instances[0]
        self._last_instance_id = instance.id
        return instance

    def _log_instance_config(self, ami_id: str, sg_id: str) -> None:
        self._log("🧾 Instance configuration:")
        self._log(f"   - Region: {self.region}")
        self._log(f"   - AMI: {ami_id}")
        self._log(f"   - InstanceType: {self.instance_type}")
        self._log(f"   - KeyName: {self.key_name or 'none'}")
        self._log(f"   - SubnetId: {self.subnet_id or 'default'}")
        self._log(f"   - VpcId: {self.vpc_id or 'default'}")
        self._log(f"   - SecurityGroupId: {sg_id}")
        self._log(f"   - IAM Profile: {self.iam_instance_profile or 'none'}")
        self._log(f"   - RootVolume: {self.root_volume_gb} GB {self.root_volume_type}")
        self._log(f"   - Public IP: {'yes' if self.associate_public_ip else 'no'}")

    def configure_elasticsearch(self, ip: str) -> None:
        """Configure Elasticsearch mappings and retention."""
        self._log("📊 Configuring Elasticsearch mappings & retention...")
        if not self._wait_for_elk(ip, timeout=240):
            raise RuntimeError("Elasticsearch not ready for configuration.")

        es = Elasticsearch(f"http://{ip}:9200", basic_auth=("elastic", self.elastic_password))

        for attempt in range(2):
            try:
                info = es.info()
                self._log(f"✅ Elasticsearch {info.get('version', {}).get('number', 'unknown')} ready.")
                break
            except Exception as exc:
                if self._is_auth_error(exc) and attempt == 0:
                    self._log("⚠️ Elasticsearch auth failed. Attempting redeploy via SSM...")
                    if self._last_instance_id and self._redeploy_elk_via_ssm(self._last_instance_id):
                        if self._wait_for_elk(ip, timeout=240):
                            es = Elasticsearch(
                                f"http://{ip}:9200", basic_auth=("elastic", self.elastic_password)
                            )
                            continue
                    raise RuntimeError("Elasticsearch authentication failed. Check elastic password.")
                self._log(f"⚠️ Could not fetch cluster info: {exc}")
                break

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
                if self._is_auth_error(exc):
                    raise RuntimeError("Elasticsearch authentication failed for ILM policy.")
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
                if self._is_auth_error(exc):
                    raise RuntimeError("Elasticsearch authentication failed for index template.")
                self._log(f"⚠️ Failed to create index template: {exc}")

        # Kibana data view
        if self._wait_for_kibana(ip, timeout=180):
            try:
                resp = requests.post(
                    f"http://{ip}:5601/api/data_views/data_view",
                    auth=("elastic", self.elastic_password),
                    json={"data_view": {"title": "suricata-*", "name": "Suricata Full Specs", "timeFieldName": "@timestamp"}},
                    headers={"kbn-xsrf": "true"},
                    timeout=10,
                )
                if resp.status_code in {200, 201, 409, 400}:
                    self._log("✅ Kibana data view ready.")
                else:
                    self._log(f"⚠️ Kibana data view response: {resp.status_code} {resp.text}")
            except requests.RequestException as exc:
                self._log(f"⚠️ Kibana data view request failed: {exc}")
        else:
            self._log("⚠️ Kibana not ready. Skipping data view configuration.")

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

    def keypair_exists(self, key_name: str) -> bool:
        if not key_name:
            return False
        try:
            self._ec2_client.describe_key_pairs(KeyNames=[key_name])
            return True
        except Exception:
            return False

    def list_tagged_instances_all_regions(self) -> list[dict[str, object]]:
        """List tagged ELK instances across all regions."""
        regions = self._ec2_client.describe_regions().get("Regions", [])
        region_names = [region["RegionName"] for region in regions]
        results: list[dict[str, object]] = []
        filters = [
            {"Name": "tag:Project", "Values": ["ids2"]},
            {"Name": "tag:Role", "Values": ["elk"]},
            {"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]},
        ]
        for region in region_names:
            client = self._session.client("ec2", region_name=region)
            try:
                response = client.describe_instances(Filters=filters)  # type: ignore[arg-type]
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

    def select_instance_to_keep(self, instances: list[dict[str, object]]):
        if not instances:
            return None
        state_rank = {"running": 0, "pending": 1, "stopping": 2, "stopped": 3}

        def sort_key(item):
            rank = state_rank.get(item.get("state"), 99)
            launch = item.get("launch_time")
            launch_ts = launch.timestamp() if isinstance(launch, datetime) else 0
            return (rank, -launch_ts)

        return sorted(instances, key=sort_key)[0]

    def terminate_instances_across_regions(self, instances: list[dict[str, object]], keep_id: str | None = None) -> None:
        for inst in instances:
            instance_id = inst.get("id")
            region = inst.get("region")
            if not instance_id or not region:
                continue
            if keep_id and str(instance_id) == keep_id:
                continue
            try:
                instance_id_str = str(instance_id)
                self._log(f"🧹 Terminating {instance_id_str} in {region}...")
                client = self._session.client("ec2", region_name=str(region))
                client.terminate_instances(InstanceIds=[instance_id_str])
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
        filters = [{"Name": "group-name", "Values": ["ids2-elk-sg"]}]
        if self.vpc_id:
            filters.append({"Name": "vpc-id", "Values": [self.vpc_id]})
        groups = self._ec2_client.describe_security_groups(Filters=filters).get("SecurityGroups", [])
        if groups:
            sg_id = groups[0]["GroupId"]
            self._log(f"✅ Reusing security group {sg_id}")
        else:
            params = {
                "GroupName": "ids2-elk-sg",
                "Description": "IDS2 ELK Access",
            }
            if self.vpc_id:
                params["VpcId"] = self.vpc_id
            sg = self.ec2.create_security_group(**params)
            sg_id = sg.id
            self._log(f"✅ Created security group {sg_id}")

        try:
            self._ec2_client.authorize_security_group_ingress(
                GroupId=sg_id,
                IpPermissions=[
                    {"IpProtocol": "tcp", "FromPort": 9200, "ToPort": 9200, "IpRanges": [{"CidrIp": f"{my_ip}/32"}]},
                    {"IpProtocol": "tcp", "FromPort": 5601, "ToPort": 5601, "IpRanges": [{"CidrIp": f"{my_ip}/32"}]},
                    {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22, "IpRanges": [{"CidrIp": f"{my_ip}/32"}]},
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

    def _probe_kibana(self, ip: str) -> bool:
        try:
            resp = requests.get(
                f"http://{ip}:5601/api/status",
                auth=("elastic", self.elastic_password),
                headers={"kbn-xsrf": "true"},
                timeout=5,
            )
            if resp.status_code in {200, 401}:
                return True
        except requests.RequestException:
            return False
        return False

    def _wait_for_kibana(self, ip: str, timeout: int = 300) -> bool:
        for _ in _tqdm(range(timeout), desc="Waiting for Kibana", unit="s"):
            if self._probe_kibana(ip):
                return True
            time.sleep(1)
        return False

    def _is_auth_error(self, exc: Exception) -> bool:
        status = getattr(exc, "status_code", None)
        if status == 401:
            return True
        return "AuthenticationException" in str(exc) or "security_exception" in str(exc)

    def _redeploy_elk_via_ssm(self, instance_id: str) -> bool:
        compose = self._build_docker_compose()
        commands = [
            "mkdir -p /home/ubuntu/elk",
            "cat <<'EOF' > /home/ubuntu/elk/docker-compose.yml\n"
            + compose
            + "\nEOF",
            "cd /home/ubuntu/elk && docker-compose down || true",
            "cd /home/ubuntu/elk && docker-compose up -d",
        ]
        return self._send_ssm_commands(instance_id, commands, log_output=True)

    def _send_ssm_commands(
        self, instance_id: str, commands: list[str], timeout: int = 240, log_output: bool = False
    ) -> bool:
        try:
            response = self.ssm.send_command(
                InstanceIds=[instance_id],
                DocumentName="AWS-RunShellScript",
                Parameters={"commands": commands},
            )
            command_id = response["Command"]["CommandId"]
        except Exception as exc:
            self._log(f"⚠️ Failed to send SSM command: {exc}")
            return False

        for _ in _tqdm(range(timeout), desc="Waiting for SSM command", unit="s"):
            try:
                result = self.ssm.get_command_invocation(
                    CommandId=command_id,
                    InstanceId=instance_id,
                )
                status = result.get("Status")
                if status in {"Success"}:
                    if log_output:
                        output = result.get("StandardOutputContent", "").strip()
                        if output:
                            self._log(f"🧾 SSM output:\n{output}")
                    return True
                if status in {"Failed", "TimedOut", "Cancelled"}:
                    self._log(f"⚠️ SSM command status: {status}")
                    return False
            except Exception:
                pass
            time.sleep(1)
        self._log("⚠️ SSM command timed out.")
        return False

    def _log_docker_status(self, instance_id: str) -> None:
        commands = [
            "docker ps -a || true",
            "cd /home/ubuntu/elk && docker-compose ps || true",
            "systemctl status docker --no-pager || true",
        ]
        self._send_ssm_commands(instance_id, commands, log_output=True)

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
