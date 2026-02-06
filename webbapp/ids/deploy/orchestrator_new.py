"""Deployment orchestrator with DB integration and SSH-only approach."""

from __future__ import annotations

import socket
import threading
import time
from typing import Callable, TYPE_CHECKING

from ..db import db

def _tqdm(iterable=None, **kwargs):
    try:
        from tqdm import tqdm  # type: ignore
        return tqdm(iterable, **kwargs)
    except Exception:
        return iterable if iterable is not None else []

from .aws_deployer import AWSDeployer
from .pi_deployer import PiDeployer
from .ssh_client import SSHClient

if TYPE_CHECKING:
    from .config import DeployConfig


class DeploymentHalted(Exception):
    """Raised when user halts deployment."""


class DeploymentOrchestrator:
    """Orchestrates IDS deployment with database integration."""
    
    def __init__(
        self,
        log_callback: Callable[[str], None],
        decision_callback: Callable[[dict], str] | None = None,
    ) -> None:
        self._log = log_callback
        self._decision_callback = decision_callback
    
    def full_deploy(self, config: DeployConfig, progress_callback: Callable[[float, str], None]) -> str:
        """
        Execute full deployment with DB integration.
        Order: Pi → Suricata → DB → EC2 → Update DB
        """
        step = 0
        total_steps = 11 + sum([config.reset_first, config.remove_docker, config.install_docker])

        progress_bar = _tqdm(total=total_steps, desc="Deployment", unit="step")

        def advance(label: str) -> None:
            nonlocal step
            step += 1
            progress_callback(step / total_steps * 100, label)
            try:
                progress_bar.set_postfix_str(label)
                progress_bar.update(1)
            except Exception:
                pass

        monitor_stop: threading.Event | None = None
        elk_ip = ""
        
        try:
            # === STEP 1: Connect to Pi ===
            self._log("🔌 Connecting to Pi...")
            advance("Connecting to Pi")
            
            with SSHClient(
                config.pi_host,
                config.pi_user,
                config.pi_password,
                config.sudo_password,
                self._log,
                ssh_key_path=config.ssh_key_path,
            ) as ssh:
                pi = PiDeployer(ssh, config)
                
                if config.reset_first:
                    self._log("🧹 Reset requested...")
                    pi.reset()
                    advance("Reset complete")

                if config.remove_docker:
                    self._log("🧹 Removing Docker...")
                    pi.remove_docker()
                    advance("Docker removed")

                if config.install_docker:
                    self._log("🐳 Installing Docker...")
                    pi.install_docker()
                    advance("Docker installed")

                # === STEP 2: Deploy Suricata ===
                self._log("🛡️ Installing Suricata probe...")
                advance("Installing Suricata")
                pi.install_probe()
                
                # === STEP 3: Deploy & Test Database ===
                self._log("💾 Deploying database...")
                advance("Deploying database")
                pi.deploy_webapp()  # This includes DB deployment
                
                self._log("🧪 Testing database health...")
                if not db.check_health():
                    self._log("⚠️ Database health check failed")
                else:
                    self._log("✅ Database is healthy")
                
                # Upload shared SSH key to Pi
                self._log("🔑 Uploading shared SSH key to Pi...")
                advance("Uploading SSH key to Pi")
                if config.ssh_key_path:
                    pi.install_shared_ssh_key(config.ssh_key_path)
                
            # === STEP 4: Check DB for existing instances ===
            self._log("🔍 Checking database for existing instances...")
            advance("Checking DB instances")
            db_instances = db.get_ec2_instances()
            
            if db_instances:
                self._log(f"📊 Found {len(db_instances)} instance(s) in database:")
                for inst in db_instances:
                    self._log(f"   - {inst['instance_id']} ({inst['state']}) in {inst['region']}")
            
            # === STEP 5: Deploy EC2 ===
            self._log("☁️ Creating AWS instance...")
            advance("Creating AWS instance")
            
            aws = AWSDeployer(
                config.aws_region,
                config.elastic_password,
                self._log,
                aws_access_key_id=config.aws_access_key_id,
                aws_secret_access_key=config.aws_secret_access_key,
                ami_id=config.aws_ami_id,
                instance_type=config.aws_instance_type,
                key_name=config.aws_key_name,
                subnet_id=config.aws_subnet_id,
                vpc_id=config.aws_vpc_id,
                security_group_id=config.aws_security_group_id,
                iam_instance_profile=config.aws_iam_instance_profile,
                root_volume_gb=config.aws_root_volume_gb,
                root_volume_type=config.aws_root_volume_type,
                associate_public_ip=config.aws_associate_public_ip,
            )
            
            # Check AWS for actual instances and reconcile with DB
            self._log("🔍 Reconciling AWS instances with database...")
            aws_instances = aws.list_tagged_instances_all_regions()
            
            for aws_inst in aws_instances:
                db.upsert_ec2_instance(
                    instance_id=aws_inst["id"],
                    region=aws_inst["region"],
                    instance_type=aws_inst.get("instance_type", ""),
                    public_ip=aws_inst.get("public_ip", ""),
                    private_ip=aws_inst.get("private_ip", ""),
                    state=aws_inst.get("state", ""),
                    elk_deployed=False,
                )
            
            instance = aws.ensure_instance()
            aws.log_ssh_access(instance)
            
            # Upload SSH key to EC2
            self._log("🔑 Uploading shared SSH key to EC2...")
            advance("Uploading SSH key to EC2")
            if config.ssh_key_path and instance.public_ip_address:
                aws.upload_ssh_key_to_instance(
                    instance.public_ip_address,
                    config.ssh_key_path,
                )

            if self._decision_callback:
                try:
                    instance.reload()
                except Exception:
                    pass
                costs = aws.estimate_costs(getattr(instance, "instance_type", None), config.aws_region)
                costs.update(
                    {
                        "instance_id": getattr(instance, "id", ""),
                        "instance_type": getattr(instance, "instance_type", ""),
                        "region": config.aws_region,
                        "public_ip": getattr(instance, "public_ip_address", ""),
                    }
                )
                action = self._decision_callback(costs)
                if action == "stop_elastic":
                    raise DeploymentHalted("User cancelled deployment (stop Elastic).")
                if action == "stop_instance":
                    aws.terminate_instance(instance)
                    raise DeploymentHalted("Instance terminated per user request.")

            self._log("🔍 Waiting for ELK to be ready...")
            advance("Waiting for ELK")
            elk_ip = aws.ensure_elk_ready(instance)

            self._log("🌐 ELK access info...")
            advance("Verifying ELK services")
            aws.log_access_info(elk_ip)
            if not aws.verify_services(elk_ip):
                raise RuntimeError("ELK services not healthy (Elasticsearch/Kibana).")

            # Start SSH health monitor
            monitor_stop = self._start_ssh_health_monitor(
                pi_host=config.pi_host,
                pi_ip=config.pi_ip,
                ec2_ip=elk_ip,
            )

            self._log("📊 Configuring Elasticsearch...")
            advance("Configuring Elasticsearch")
            aws.configure_elasticsearch(elk_ip)

            # === STEP 6: Update Database ===
            self._log("💾 Updating database with deployment info...")
            advance("Updating database")
            
            # Update EC2 instance in DB
            instance.reload()
            db.upsert_ec2_instance(
                instance_id=instance.id,
                region=config.aws_region,
                instance_type=instance.instance_type,
                public_ip=instance.public_ip_address or "",
                private_ip=instance.private_ip_address or "",
                state=(instance.state or {}).get("Name", ""),
                elk_deployed=True,
            )
            
            # Save deployment config
            db.save_deployment_config(
                aws_region=config.aws_region,
                elk_ip=elk_ip,
                elastic_password=config.elastic_password,
                pi_host=config.pi_host,
                pi_user=config.pi_user,
                pi_password=config.pi_password,
                sudo_password=config.sudo_password,
                remote_dir=config.remote_dir,
                mirror_interface=config.mirror_interface,
                ssh_key_path=config.ssh_key_path,
            )
            
            self._log("✅ Database updated with deployment information")

            # Continue with Pi streamer
            with SSHClient(
                config.pi_host,
                config.pi_user,
                config.pi_password,
                config.sudo_password,
                self._log,
                ssh_key_path=config.ssh_key_path,
            ) as ssh:
                pi = PiDeployer(ssh, config)
                
                self._log("📡 Installing streamer...")
                advance("Installing streamer")
                pi.install_streamer(elk_ip, config.elastic_password)

            return elk_ip
        finally:
            try:
                progress_bar.close()
            except Exception:
                pass
            if monitor_stop:
                monitor_stop.set()

    def reset_only(self, config: DeployConfig, progress_callback: Callable[[float, str], None]) -> None:
        """Reset Pi only."""
        progress_callback(5, "Connecting to Pi")
        with SSHClient(
            config.pi_host,
            config.pi_user,
            config.pi_password,
            config.sudo_password,
            self._log,
            ssh_key_path=config.ssh_key_path,
        ) as ssh:
            pi = PiDeployer(ssh, config)
            pi.reset()
        progress_callback(100, "Reset complete")

    def install_docker_only(self, config: DeployConfig, progress_callback: Callable[[float, str], None]) -> None:
        """Install Docker only."""
        progress_callback(10, "Connecting to Pi")
        with SSHClient(
            config.pi_host,
            config.pi_user,
            config.pi_password,
            config.sudo_password,
            self._log,
            ssh_key_path=config.ssh_key_path,
        ) as ssh:
            pi = PiDeployer(ssh, config)
            pi.install_docker()
        progress_callback(100, "Docker installed")

    def remove_docker_only(self, config: DeployConfig, progress_callback: Callable[[float, str], None]) -> None:
        """Remove Docker only."""
        progress_callback(10, "Connecting to Pi")
        with SSHClient(
            config.pi_host,
            config.pi_user,
            config.pi_password,
            config.sudo_password,
            self._log,
            ssh_key_path=config.ssh_key_path,
        ) as ssh:
            pi = PiDeployer(ssh, config)
            pi.remove_docker()
        progress_callback(100, "Docker removed")

    def _start_ssh_health_monitor(self, pi_host: str, pi_ip: str, ec2_ip: str) -> threading.Event:
        """Start background thread to monitor SSH health every 10 seconds."""
        stop_event = threading.Event()
        pi_target = pi_host or pi_ip

        def _monitor_loop() -> None:
            while not stop_event.is_set():
                pi_ok = self._check_ssh(pi_target, 22)
                ec2_ok = self._check_ssh(ec2_ip, 22)
                self._log(
                    f"🔁 SSH Health (Pi: {pi_target}) "
                    f"{'✅' if pi_ok else '❌'} | "
                    f"(EC2: {ec2_ip}) {'✅' if ec2_ok else '❌'}"
                )
                stop_event.wait(10)

        thread = threading.Thread(target=_monitor_loop, daemon=True)
        thread.start()
        return stop_event

    def _check_ssh(self, host: str, port: int) -> bool:
        """Check if SSH port is reachable."""
        if not host:
            return False
        try:
            with socket.create_connection((host, port), timeout=3):
                return True
        except OSError:
            return False
