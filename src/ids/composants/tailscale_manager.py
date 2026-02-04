"""
TailscaleManager - Manages Tailscale network architecture.

Provides functionality to:
- Create and manage tailnets
- Add/remove nodes (including third-party)
- Automatic deployment mode selection (Linux service, Docker, Docker Compose)
- Generate auth keys for node registration
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..app.decorateurs import cache_resultat, log_appel, metriques, retry
from ..domain import ConditionSante
from ..domain.tailscale import (
    DeploymentMode,
    DeploymentResult,
    NodeStatus,
    NodeType,
    TailnetConfig,
    TailscaleAuthKey,
    TailscaleDeploymentConfig,
    TailscaleNode,
)
from ..interfaces import GestionnaireConfig
from .base import BaseComponent

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


# Deployment strategy decorator
def deployment_strategy(mode: DeploymentMode):
    """Decorator to mark a method as a deployment strategy for a specific mode."""

    def decorator(func: Callable) -> Callable:
        func._deployment_mode = mode
        return func

    return decorator


# Node type handler decorator
def handles_node_type(*node_types: NodeType):
    """Decorator to mark a method as handling specific node types."""

    def decorator(func: Callable) -> Callable:
        func._handled_node_types = node_types
        return func

    return decorator


@dataclass
class DeploymentCapabilities:
    """Capabilities detected on the target system for deployment."""

    has_systemd: bool = False
    has_docker: bool = False
    has_docker_compose: bool = False
    is_in_container: bool = False
    tailscale_installed: bool = False
    tailscale_running: bool = False
    platform: str = "unknown"
    details: Dict[str, Any] = field(default_factory=dict)


class TailscaleManager(BaseComponent):
    """
    Manages Tailscale network architecture.

    Provides methods to:
    - Create auth keys for node registration
    - Add nodes to the tailnet (with automatic deployment mode selection)
    - Remove nodes from the tailnet
    - List and monitor nodes
    - Configure routing and ACLs

    Deployment modes:
    - LINUX_SERVICE: Systemd service on host (best for dedicated servers/Pi)
    - DOCKER: Standalone Docker container (good for isolated deployment)
    - DOCKER_COMPOSE: Part of docker-compose stack (integrated with other services)
    - SIDECAR: Sidecar pattern for existing containers
    """

    SYSTEMD_SERVICE_TEMPLATE = """[Unit]
Description=Tailscale node daemon
Documentation=https://tailscale.com/kb/
Wants=network-pre.target
After=network-pre.target NetworkManager.service systemd-resolved.service

[Service]
ExecStartPre=/usr/sbin/tailscaled --cleanup
ExecStart=/usr/sbin/tailscaled --state=/var/lib/tailscale/tailscaled.state --socket=/run/tailscale/tailscaled.sock --port=41641
ExecStopPost=/usr/sbin/tailscaled --cleanup
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""

    DOCKER_COMPOSE_TEMPLATE = """
  tailscale:
    image: tailscale/tailscale:latest
    container_name: tailscale
    hostname: {hostname}
    privileged: true
    network_mode: host
    cap_add:
      - NET_ADMIN
      - SYS_MODULE
    volumes:
      - /dev/net/tun:/dev/net/tun
      - tailscale-state:/var/lib/tailscale
    environment:
      - TS_AUTHKEY={auth_key}
      - TS_EXTRA_ARGS={extra_args}
      - TS_STATE_DIR=/var/lib/tailscale
    restart: unless-stopped
"""

    DOCKERFILE_TEMPLATE = """FROM tailscale/tailscale:latest

ENV TS_AUTHKEY={auth_key}
ENV TS_EXTRA_ARGS={extra_args}
ENV TS_STATE_DIR=/var/lib/tailscale

VOLUME /var/lib/tailscale

CMD ["tailscaled"]
"""

    def __init__(self, config: Optional[GestionnaireConfig] = None) -> None:
        super().__init__(config, "tailscale")
        self._tailnet_config: Optional[TailnetConfig] = None
        self._nodes: Dict[str, TailscaleNode] = {}
        self._auth_keys: Dict[str, TailscaleAuthKey] = {}
        self._deployment_strategies: Dict[DeploymentMode, Callable] = {}
        self._register_deployment_strategies()
        self._load_config()

    def _load_config(self) -> None:
        """Load Tailscale configuration from config manager."""
        if not self._config:
            return

        tailnet = self._config.obtenir("tailscale.tailnet")
        if not tailnet:
            return

        self._tailnet_config = TailnetConfig(
            tailnet=tailnet,
            api_key=self._config.obtenir("tailscale.api_key"),
            oauth_client_id=self._config.obtenir("tailscale.oauth_client_id"),
            oauth_client_secret=self._config.obtenir("tailscale.oauth_client_secret"),
            auth_key=self._config.obtenir("tailscale.auth_key"),
            default_tags=self._config.obtenir("tailscale.default_tags", []),
            dns_enabled=self._config.obtenir("tailscale.dns_enabled", True),
            magic_dns=self._config.obtenir("tailscale.magic_dns", True),
            exit_node_enabled=self._config.obtenir("tailscale.exit_node_enabled", False),
            subnet_routes=self._config.obtenir("tailscale.subnet_routes", []),
        )

    def _register_deployment_strategies(self) -> None:
        """Register deployment strategy methods."""
        self._deployment_strategies = {
            DeploymentMode.LINUX_SERVICE: self._deploy_linux_service,
            DeploymentMode.DOCKER: self._deploy_docker,
            DeploymentMode.DOCKER_COMPOSE: self._deploy_docker_compose,
            DeploymentMode.SIDECAR: self._deploy_sidecar,
        }

    @log_appel()
    @metriques("tailscale.detect_capabilities")
    async def detect_capabilities(
        self,
        target_host: Optional[str] = None,
        ssh_key: Optional[str] = None,
    ) -> DeploymentCapabilities:
        """
        Detect deployment capabilities on the target system.

        Args:
            target_host: Remote host to check (None for local)
            ssh_key: SSH key path for remote connection

        Returns:
            DeploymentCapabilities with detected features
        """
        caps = DeploymentCapabilities()

        def run_cmd(cmd: List[str]) -> Tuple[bool, str]:
            """Run command locally or remotely."""
            try:
                if target_host:
                    ssh_cmd = ["ssh"]
                    if ssh_key:
                        ssh_cmd.extend(["-i", ssh_key])
                    ssh_cmd.extend([target_host, " ".join(cmd)])
                    result = subprocess.run(
                        ssh_cmd,
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                else:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                return result.returncode == 0, result.stdout.strip()
            except (subprocess.TimeoutExpired, FileNotFoundError):
                return False, ""

        # Check systemd
        caps.has_systemd, _ = run_cmd(["systemctl", "--version"])

        # Check Docker
        caps.has_docker, _ = run_cmd(["docker", "--version"])

        # Check Docker Compose
        caps.has_docker_compose, _ = run_cmd(["docker", "compose", "version"])

        # Check if running inside container
        caps.is_in_container = os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv")

        # Check Tailscale installation
        caps.tailscale_installed, version = run_cmd(["tailscale", "--version"])
        if caps.tailscale_installed:
            caps.details["tailscale_version"] = version

        # Check Tailscale status
        caps.tailscale_running, status = run_cmd(["tailscale", "status", "--json"])
        if status:
            try:
                caps.details["tailscale_status"] = json.loads(status)
            except json.JSONDecodeError:
                pass

        # Detect platform
        _, platform = run_cmd(["uname", "-s"])
        caps.platform = platform.lower() if platform else "unknown"

        return caps

    @log_appel()
    @metriques("tailscale.select_deployment_mode")
    def select_best_deployment_mode(self, caps: DeploymentCapabilities) -> DeploymentMode:
        """
        Select the best deployment mode based on detected capabilities.

        Priority:
        1. If in container -> SIDECAR
        2. If systemd available and not in container -> LINUX_SERVICE
        3. If Docker Compose available -> DOCKER_COMPOSE
        4. If Docker available -> DOCKER
        5. Fallback to LINUX_SERVICE

        Args:
            caps: Detected deployment capabilities

        Returns:
            Best DeploymentMode for the target system
        """
        # Inside container: use sidecar pattern
        if caps.is_in_container:
            if caps.has_docker:
                return DeploymentMode.SIDECAR
            return DeploymentMode.DOCKER

        # Native systemd is best for dedicated hosts
        if caps.has_systemd and not caps.is_in_container:
            return DeploymentMode.LINUX_SERVICE

        # Docker Compose for integrated deployments
        if caps.has_docker_compose:
            return DeploymentMode.DOCKER_COMPOSE

        # Standalone Docker
        if caps.has_docker:
            return DeploymentMode.DOCKER

        # Fallback
        return DeploymentMode.LINUX_SERVICE

    @log_appel()
    @metriques("tailscale.create_authkey")
    @retry(nb_tentatives=3, delai_initial=1.0, backoff=2.0)
    async def create_auth_key(
        self,
        reusable: bool = False,
        ephemeral: bool = False,
        preauthorized: bool = True,
        tags: Optional[List[str]] = None,
        expiry_seconds: int = 86400,
        description: Optional[str] = None,
    ) -> TailscaleAuthKey:
        """
        Create a new auth key for node registration.

        Args:
            reusable: Allow key to be used multiple times
            ephemeral: Create ephemeral nodes (auto-deleted when offline)
            preauthorized: Skip admin authorization step
            tags: Tags to apply to nodes using this key
            expiry_seconds: Key expiration time in seconds
            description: Human-readable description

        Returns:
            TailscaleAuthKey with the generated key

        Raises:
            ValueError: If tailnet config is missing
            RuntimeError: If API call fails
        """
        if not self._tailnet_config:
            raise ValueError("Tailnet configuration not loaded")

        # Build auth key request
        key_tags = tags or self._tailnet_config.default_tags
        expires_at = _utcnow() + timedelta(seconds=expiry_seconds)

        # Use Tailscale API to create key
        api_key = self._tailnet_config.api_key
        if not api_key:
            raise ValueError("Tailscale API key not configured")

        payload = {
            "capabilities": {
                "devices": {
                    "create": {
                        "reusable": reusable,
                        "ephemeral": ephemeral,
                        "preauthorized": preauthorized,
                        "tags": [f"tag:{t}" if not t.startswith("tag:") else t for t in key_tags],
                    }
                }
            },
            "expirySeconds": expiry_seconds,
            "description": description or f"IDS2 auto-generated key at {_utcnow().isoformat()}",
        }

        def _create_key() -> Dict[str, Any]:
            import urllib.request

            url = f"https://api.tailscale.com/api/v2/tailnet/{self._tailnet_config.tailnet}/keys"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            data = json.dumps(payload).encode("utf-8")

            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))

        result = await asyncio.to_thread(_create_key)

        auth_key = TailscaleAuthKey(
            key=result.get("key", ""),
            key_id=result.get("id", ""),
            created_at=_utcnow(),
            expires_at=expires_at,
            reusable=reusable,
            ephemeral=ephemeral,
            preauthorized=preauthorized,
            tags=key_tags,
            description=description,
        )

        self._auth_keys[auth_key.key_id] = auth_key
        logger.info("Created auth key: %s (expires: %s)", auth_key.key_id, expires_at)
        return auth_key

    @log_appel()
    @metriques("tailscale.add_node")
    @retry(nb_tentatives=2, delai_initial=2.0, backoff=2.0)
    @handles_node_type(NodeType.DEVICE, NodeType.THIRD_PARTY, NodeType.SUBNET_ROUTER)
    async def add_node(
        self,
        hostname: str,
        auth_key: Optional[str] = None,
        node_type: NodeType = NodeType.DEVICE,
        deployment_mode: Optional[DeploymentMode] = None,
        target_host: Optional[str] = None,
        ssh_key: Optional[str] = None,
        ssh_user: str = "pi",
        advertise_routes: Optional[List[str]] = None,
        advertise_exit_node: bool = False,
        tags: Optional[List[str]] = None,
    ) -> DeploymentResult:
        """
        Add a new node to the tailnet.

        Automatically selects the best deployment mode if not specified.

        Args:
            hostname: Name for the new node
            auth_key: Auth key for registration (or creates one)
            node_type: Type of node to create
            deployment_mode: Force specific deployment mode
            target_host: Remote host IP/hostname (None for local)
            ssh_key: SSH key path for remote deployment
            ssh_user: SSH username for remote deployment
            advertise_routes: Subnet routes to advertise
            advertise_exit_node: Configure as exit node
            tags: Tags to apply to the node

        Returns:
            DeploymentResult with success status and node details
        """
        try:
            # Detect capabilities
            caps = await self.detect_capabilities(target_host, ssh_key)

            # Select deployment mode
            if deployment_mode is None:
                deployment_mode = self.select_best_deployment_mode(caps)

            logger.info(
                "Deploying Tailscale node '%s' using %s mode",
                hostname,
                deployment_mode.name,
            )

            # Get or create auth key
            if not auth_key:
                if self._tailnet_config and self._tailnet_config.auth_key:
                    auth_key = self._tailnet_config.auth_key
                else:
                    new_key = await self.create_auth_key(
                        reusable=False,
                        ephemeral=False,
                        preauthorized=True,
                        tags=tags,
                        description=f"Auto-key for {hostname}",
                    )
                    auth_key = new_key.key

            # Build deployment config
            deploy_config = TailscaleDeploymentConfig(
                mode=deployment_mode,
                auth_key=auth_key,
                hostname=hostname,
                advertise_exit_node=advertise_exit_node,
                advertise_routes=advertise_routes or [],
                tags=tags or [],
            )

            # Execute deployment strategy
            strategy = self._deployment_strategies.get(deployment_mode)
            if not strategy:
                raise ValueError(f"No deployment strategy for mode: {deployment_mode}")

            result = await strategy(
                deploy_config=deploy_config,
                target_host=target_host,
                ssh_key=ssh_key,
                ssh_user=ssh_user,
                capabilities=caps,
            )

            if result.success and result.node:
                self._nodes[result.node.hostname] = result.node

            return result

        except Exception as e:
            logger.error("Failed to add node '%s': %s", hostname, e)
            return DeploymentResult(
                success=False,
                mode=deployment_mode,
                message=f"Deployment failed: {e}",
                error=str(e),
            )

    @deployment_strategy(DeploymentMode.LINUX_SERVICE)
    async def _deploy_linux_service(
        self,
        deploy_config: TailscaleDeploymentConfig,
        target_host: Optional[str],
        ssh_key: Optional[str],
        ssh_user: str,
        capabilities: DeploymentCapabilities,
    ) -> DeploymentResult:
        """Deploy Tailscale as a Linux systemd service."""

        def run_remote(cmd: str) -> subprocess.CompletedProcess:
            if target_host:
                ssh_cmd = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new"]
                if ssh_key:
                    ssh_cmd.extend(["-i", ssh_key])
                ssh_cmd.append(f"{ssh_user}@{target_host}")
                ssh_cmd.append(cmd)
                return subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=120)
            else:
                return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)

        try:
            # Install Tailscale if not present
            if not capabilities.tailscale_installed:
                logger.info("Installing Tailscale on target...")
                install_result = run_remote("curl -fsSL https://tailscale.com/install.sh | sh")
                if install_result.returncode != 0:
                    return DeploymentResult(
                        success=False,
                        mode=DeploymentMode.LINUX_SERVICE,
                        message="Failed to install Tailscale",
                        error=install_result.stderr,
                    )

            # Enable and start tailscaled
            run_remote("sudo systemctl enable tailscaled")
            run_remote("sudo systemctl start tailscaled")

            # Run tailscale up with auth key
            up_args = deploy_config.to_tailscale_up_args()
            up_cmd = f"sudo tailscale up {' '.join(up_args)}"
            result = run_remote(up_cmd)

            if result.returncode != 0:
                return DeploymentResult(
                    success=False,
                    mode=DeploymentMode.LINUX_SERVICE,
                    message="Failed to authenticate with Tailscale",
                    error=result.stderr,
                )

            # Get status to confirm
            status_result = run_remote("tailscale status --json")
            status_data = {}
            if status_result.returncode == 0:
                try:
                    status_data = json.loads(status_result.stdout)
                except json.JSONDecodeError:
                    pass

            node = TailscaleNode(
                hostname=deploy_config.hostname or "unknown",
                node_type=NodeType.DEVICE,
                status=NodeStatus.ONLINE,
                authorized=True,
                deployment_mode=DeploymentMode.LINUX_SERVICE,
                tailnet_ip=status_data.get("Self", {}).get("TailscaleIPs", [None])[0],
                created_at=_utcnow(),
                last_seen=_utcnow(),
                tags=deploy_config.tags,
                advertised_routes=deploy_config.advertise_routes,
            )

            return DeploymentResult(
                success=True,
                node=node,
                mode=DeploymentMode.LINUX_SERVICE,
                message="Tailscale deployed as Linux service",
                details={"status": status_data},
            )

        except Exception as e:
            return DeploymentResult(
                success=False,
                mode=DeploymentMode.LINUX_SERVICE,
                message=f"Linux service deployment failed: {e}",
                error=str(e),
            )

    @deployment_strategy(DeploymentMode.DOCKER)
    async def _deploy_docker(
        self,
        deploy_config: TailscaleDeploymentConfig,
        target_host: Optional[str],
        ssh_key: Optional[str],
        ssh_user: str,
        capabilities: DeploymentCapabilities,
    ) -> DeploymentResult:
        """Deploy Tailscale as a standalone Docker container."""

        def run_remote(cmd: str) -> subprocess.CompletedProcess:
            if target_host:
                ssh_cmd = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new"]
                if ssh_key:
                    ssh_cmd.extend(["-i", ssh_key])
                ssh_cmd.append(f"{ssh_user}@{target_host}")
                ssh_cmd.append(cmd)
                return subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=120)
            else:
                return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)

        try:
            extra_args = " ".join(deploy_config.to_tailscale_up_args())

            # Run Tailscale container
            docker_cmd = (
                f"docker run -d "
                f"--name tailscale-{deploy_config.hostname} "
                f"--hostname {deploy_config.hostname} "
                f"--privileged "
                f"--network host "
                f"--cap-add NET_ADMIN "
                f"--cap-add SYS_MODULE "
                f"-v /dev/net/tun:/dev/net/tun "
                f"-v tailscale-{deploy_config.hostname}-state:/var/lib/tailscale "
                f"-e TS_AUTHKEY={deploy_config.auth_key} "
                f'-e TS_EXTRA_ARGS="{extra_args}" '
                f"-e TS_STATE_DIR=/var/lib/tailscale "
                f"--restart unless-stopped "
                f"tailscale/tailscale:latest"
            )

            result = run_remote(docker_cmd)

            if result.returncode != 0:
                return DeploymentResult(
                    success=False,
                    mode=DeploymentMode.DOCKER,
                    message="Failed to start Docker container",
                    error=result.stderr,
                )

            # Wait for container to initialize
            await asyncio.sleep(5)

            node = TailscaleNode(
                hostname=deploy_config.hostname or "unknown",
                node_type=NodeType.DEVICE,
                status=NodeStatus.PENDING,
                authorized=True,
                deployment_mode=DeploymentMode.DOCKER,
                created_at=_utcnow(),
                tags=deploy_config.tags,
                advertised_routes=deploy_config.advertise_routes,
                metadata={"container_name": f"tailscale-{deploy_config.hostname}"},
            )

            return DeploymentResult(
                success=True,
                node=node,
                mode=DeploymentMode.DOCKER,
                message="Tailscale deployed as Docker container",
                details={"container_id": result.stdout.strip()},
            )

        except Exception as e:
            return DeploymentResult(
                success=False,
                mode=DeploymentMode.DOCKER,
                message=f"Docker deployment failed: {e}",
                error=str(e),
            )

    @deployment_strategy(DeploymentMode.DOCKER_COMPOSE)
    async def _deploy_docker_compose(
        self,
        deploy_config: TailscaleDeploymentConfig,
        target_host: Optional[str],
        ssh_key: Optional[str],
        ssh_user: str,
        capabilities: DeploymentCapabilities,
    ) -> DeploymentResult:
        """Deploy Tailscale as part of docker-compose stack."""
        try:
            extra_args = " ".join(deploy_config.to_tailscale_up_args())

            # Generate docker-compose snippet
            compose_snippet = self.DOCKER_COMPOSE_TEMPLATE.format(
                hostname=deploy_config.hostname,
                auth_key=deploy_config.auth_key,
                extra_args=extra_args,
            )

            # Write to temp file or append to existing compose
            compose_path = Path("/tmp/tailscale-compose.yml")
            full_compose = f"""version: '3.8'
services:
{compose_snippet}
volumes:
  tailscale-state:
"""
            compose_path.write_text(full_compose)

            # If remote, copy compose file
            if target_host:
                scp_cmd = ["scp"]
                if ssh_key:
                    scp_cmd.extend(["-i", ssh_key])
                scp_cmd.extend([str(compose_path), f"{ssh_user}@{target_host}:/tmp/"])
                subprocess.run(scp_cmd, check=True, timeout=30)

                ssh_cmd = ["ssh", "-o", "BatchMode=yes"]
                if ssh_key:
                    ssh_cmd.extend(["-i", ssh_key])
                ssh_cmd.extend(
                    [
                        f"{ssh_user}@{target_host}",
                        "cd /tmp && docker compose -f tailscale-compose.yml up -d",
                    ]
                )
                result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=120)
            else:
                result = subprocess.run(
                    ["docker", "compose", "-f", str(compose_path), "up", "-d"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

            if result.returncode != 0:
                return DeploymentResult(
                    success=False,
                    mode=DeploymentMode.DOCKER_COMPOSE,
                    message="Failed to start docker-compose stack",
                    error=result.stderr,
                )

            node = TailscaleNode(
                hostname=deploy_config.hostname or "unknown",
                node_type=NodeType.DEVICE,
                status=NodeStatus.PENDING,
                authorized=True,
                deployment_mode=DeploymentMode.DOCKER_COMPOSE,
                created_at=_utcnow(),
                tags=deploy_config.tags,
                advertised_routes=deploy_config.advertise_routes,
                metadata={"compose_file": str(compose_path)},
            )

            return DeploymentResult(
                success=True,
                node=node,
                mode=DeploymentMode.DOCKER_COMPOSE,
                message="Tailscale deployed via docker-compose",
                details={"compose_file": str(compose_path)},
            )

        except Exception as e:
            return DeploymentResult(
                success=False,
                mode=DeploymentMode.DOCKER_COMPOSE,
                message=f"Docker Compose deployment failed: {e}",
                error=str(e),
            )

    @deployment_strategy(DeploymentMode.SIDECAR)
    async def _deploy_sidecar(
        self,
        deploy_config: TailscaleDeploymentConfig,
        target_host: Optional[str],
        ssh_key: Optional[str],
        ssh_user: str,
        capabilities: DeploymentCapabilities,
    ) -> DeploymentResult:
        """Deploy Tailscale as a sidecar container."""
        # Sidecar is similar to Docker but intended for existing compose stacks
        return await self._deploy_docker(
            deploy_config, target_host, ssh_key, ssh_user, capabilities
        )

    @log_appel()
    @metriques("tailscale.remove_node")
    async def remove_node(
        self,
        hostname: str,
        target_host: Optional[str] = None,
        ssh_key: Optional[str] = None,
        ssh_user: str = "pi",
    ) -> bool:
        """
        Remove a node from the tailnet.

        Args:
            hostname: Name of the node to remove
            target_host: Remote host IP/hostname
            ssh_key: SSH key path for remote connection
            ssh_user: SSH username

        Returns:
            True if removal was successful
        """
        try:
            node = self._nodes.get(hostname)
            if not node:
                logger.warning("Node '%s' not found in local registry", hostname)

            def run_remote(cmd: str) -> subprocess.CompletedProcess:
                if target_host:
                    ssh_cmd = ["ssh", "-o", "BatchMode=yes"]
                    if ssh_key:
                        ssh_cmd.extend(["-i", ssh_key])
                    ssh_cmd.extend([f"{ssh_user}@{target_host}", cmd])
                    return subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=60)
                else:
                    return subprocess.run(
                        cmd, shell=True, capture_output=True, text=True, timeout=60
                    )

            # Determine deployment mode
            mode = node.deployment_mode if node else None

            if mode == DeploymentMode.DOCKER or mode == DeploymentMode.SIDECAR:
                # Stop and remove container
                run_remote(f"docker stop tailscale-{hostname}")
                run_remote(f"docker rm tailscale-{hostname}")
            elif mode == DeploymentMode.DOCKER_COMPOSE:
                # Get compose file path from metadata or use default
                compose_file = "/tmp/tailscale-compose.yml"
                if node and node.metadata.get("compose_file"):
                    compose_file = node.metadata["compose_file"]
                run_remote(f"docker compose -f {compose_file} down")
            else:
                # Linux service
                run_remote("sudo tailscale logout")
                run_remote("sudo systemctl stop tailscaled")

            # Remove from local registry
            if hostname in self._nodes:
                del self._nodes[hostname]

            logger.info("Node '%s' removed successfully", hostname)
            return True

        except Exception as e:
            logger.error("Failed to remove node '%s': %s", hostname, e)
            return False

    @log_appel()
    @metriques("tailscale.list_nodes")
    @cache_resultat(ttl_secondes=30)
    async def list_nodes(self) -> List[TailscaleNode]:
        """
        List all nodes in the tailnet.

        Returns:
            List of TailscaleNode objects
        """
        if not self._tailnet_config or not self._tailnet_config.api_key:
            # Return locally tracked nodes only
            return list(self._nodes.values())

        try:
            api_key = self._tailnet_config.api_key
            tailnet = self._tailnet_config.tailnet

            def _fetch_devices() -> List[Dict[str, Any]]:
                import urllib.request

                url = f"https://api.tailscale.com/api/v2/tailnet/{tailnet}/devices"
                headers = {"Authorization": f"Bearer {api_key}"}

                req = urllib.request.Request(url, headers=headers, method="GET")
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data.get("devices", [])

            devices = await asyncio.to_thread(_fetch_devices)

            nodes = []
            for device in devices:
                addresses = device.get("addresses") or []
                tailnet_ip = addresses[0] if addresses else None
                node = TailscaleNode(
                    hostname=device.get("hostname", "unknown"),
                    node_id=device.get("id"),
                    ip_addresses=addresses,
                    tailnet_ip=tailnet_ip,
                    status=NodeStatus.ONLINE if device.get("online") else NodeStatus.OFFLINE,
                    authorized=device.get("authorized", False),
                    last_seen=(
                        datetime.fromisoformat(device["lastSeen"].replace("Z", "+00:00"))
                        if device.get("lastSeen")
                        else None
                    ),
                    created_at=(
                        datetime.fromisoformat(device["created"].replace("Z", "+00:00"))
                        if device.get("created")
                        else None
                    ),
                    tags=[t.replace("tag:", "") for t in device.get("tags", [])],
                )
                nodes.append(node)
                # Update local registry
                self._nodes[node.hostname] = node

            return nodes

        except Exception as e:
            logger.error("Failed to list nodes from API: %s", e)
            return list(self._nodes.values())

    @log_appel()
    @metriques("tailscale.health")
    async def verifier_sante(self) -> ConditionSante:
        """Check Tailscale manager health."""
        try:
            caps = await self.detect_capabilities()
            tailscale_ok = caps.tailscale_running

            return ConditionSante(
                nom_composant=self.nom_composant,
                sain=tailscale_ok,
                message="Tailscale connecté" if tailscale_ok else "Tailscale déconnecté",
                details={
                    "tailscale_installed": caps.tailscale_installed,
                    "tailscale_running": caps.tailscale_running,
                    "nodes_count": len(self._nodes),
                    "has_config": self._tailnet_config is not None,
                },
            )
        except Exception as e:
            return ConditionSante(
                nom_composant=self.nom_composant,
                sain=False,
                message=f"Erreur vérification santé: {e}",
                details={"error": str(e)},
            )

    def generate_systemd_service(self) -> str:
        """Generate a systemd service file for Tailscale."""
        return self.SYSTEMD_SERVICE_TEMPLATE

    def generate_compose_snippet(self, hostname: str, auth_key: str, extra_args: str = "") -> str:
        """Generate a docker-compose snippet for Tailscale."""
        return self.DOCKER_COMPOSE_TEMPLATE.format(
            hostname=hostname,
            auth_key=auth_key,
            extra_args=extra_args,
        )

    def generate_dockerfile(self, auth_key: str, extra_args: str = "") -> str:
        """Generate a Dockerfile for Tailscale."""
        return self.DOCKERFILE_TEMPLATE.format(auth_key=auth_key, extra_args=extra_args)


__all__ = [
    "TailscaleManager",
    "DeploymentCapabilities",
    "deployment_strategy",
    "handles_node_type",
]
