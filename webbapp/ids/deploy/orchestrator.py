"""Deployment orchestrator facade."""

from __future__ import annotations

import socket
import threading
import time
from typing import Callable, TYPE_CHECKING


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
    """Raised when user stops the deployment."""


class DeploymentOrchestrator:
    """Orchestrates full IDS deployment."""
    
    def __init__(
        self,
        log_callback: Callable[[str], None],
        decision_callback: Callable[[dict], str] | None = None,
    ) -> None:
        self._log = log_callback
        self._decision_callback = decision_callback

    def full_deploy(self, config: DeployConfig, progress_callback: Callable[[float, str], None]) -> str:
        """Execute full deployment, returns ELK IP."""
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
        try:
            with SSHClient(
                config.pi_host,
                config.pi_user,
                config.pi_password,
                config.sudo_password,
                self._log,
                ssh_key_path=config.ssh_key_path,
            ) as ssh:
                pi = PiDeployer(ssh, config)
                
                self._log("🔌 Connecting to Pi...")
                advance("Connecting to Pi")
                
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
                    aws_private_key_path=config.aws_private_key_path,
                    aws_public_key_path=config.aws_public_key_path,
                    root_volume_gb=config.aws_root_volume_gb,
                    root_volume_type=config.aws_root_volume_type,
                    associate_public_ip=config.aws_associate_public_ip,
                )
                instance = aws.ensure_instance()
                aws.log_ssh_access(instance, config.aws_private_key_path)

                if aws.sync_instance_public_key(getattr(instance, "id", "")):
                    self._log("✅ EC2 public key synced to instance.")
                else:
                    self._log("⚠️ EC2 public key not synced to instance.")
                pi.install_ec2_key(
                    config.aws_private_key_path,
                    config.aws_public_key_path,
                    config.pi_ec2_key_path,
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
                        ok = aws.stop_elasticsearch(getattr(instance, "id", ""))
                        raise DeploymentHalted(
                            "Elasticsearch stopped per user request."
                            if ok
                            else "Failed to stop Elasticsearch via SSM."
                        )
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

                monitor_stop = self._start_connectivity_monitor(
                    pi_host=config.pi_host,
                    pi_ip=config.pi_ip,
                    ec2_ip=elk_ip,
                )

                self._log("📊 Configuring Elasticsearch...")
                advance("Configuring Elasticsearch")
                aws.configure_elasticsearch(elk_ip)

                self._log("🛡️ Installing probe...")
                advance("Installing probe")
                pi.install_probe()

                self._log("📦 Uploading webapp...")
                advance("Uploading webapp")
                pi.upload_webapp_files()

                self._log("🐍 Installing webapp dependencies...")
                advance("Installing webapp deps")
                pi.install_webapp_deps()

                self._log("🧩 Starting webapp service...")
                advance("Configuring webapp")
                pi.configure_webapp_service()

                self._log("📡 Installing streamer...")
                advance("Installing streamer")
                pi.install_streamer(elk_ip, config.elastic_password)

                self._log("💾 Saving config...")
                advance("Saving config")
                pi.save_config(elk_ip)

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

    def _start_connectivity_monitor(self, pi_host: str, pi_ip: str, ec2_ip: str) -> threading.Event:
        stop_event = threading.Event()
        pi_target = pi_host or pi_ip

        def _loop() -> None:
            while not stop_event.is_set():
                pi_ok = self._check_tcp(pi_target, 22)
                ec2_ok = self._check_tcp(ec2_ip, 22)
                self._log(
                    f"🔁 SSH check (Pi: {pi_target}) "
                    f"{'✅' if pi_ok else '❌'} | "
                    f"(EC2: {ec2_ip}) {'✅' if ec2_ok else '❌'}"
                )
                stop_event.wait(10)

        thread = threading.Thread(target=_loop, daemon=True)
        thread.start()
        return stop_event

    def _check_tcp(self, host: str, port: int) -> bool:
        if not host:
            return False
        try:
            with socket.create_connection((host, port), timeout=3):
                return True
        except OSError:
            return False
