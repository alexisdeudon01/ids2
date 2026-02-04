"""
Domain models for Tailscale network management.

Defines data structures for nodes, tailnet configuration, and deployment modes.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any


def _utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class DeploymentMode(Enum):
    """Deployment mode for Tailscale on a node."""

    LINUX_SERVICE = auto()  # Systemd service on host
    DOCKER = auto()  # Standalone Docker container
    DOCKER_COMPOSE = auto()  # Part of docker-compose stack
    SIDECAR = auto()  # Sidecar container in existing pod/compose


class NodeStatus(Enum):
    """Status of a Tailscale node."""

    ONLINE = "online"
    OFFLINE = "offline"
    PENDING = "pending"
    AUTHORIZED = "authorized"
    UNAUTHORIZED = "unauthorized"
    EXPIRED = "expired"


class NodeType(Enum):
    """Type of Tailscale node."""

    DEVICE = "device"  # Standard device (Pi, server, etc.)
    EXIT_NODE = "exit_node"  # Exit node for routing
    SUBNET_ROUTER = "subnet_router"  # Advertises subnets
    RELAY = "relay"  # DERP relay
    THIRD_PARTY = "third_party"  # External/third-party device


@dataclass
class TailscaleNode:
    """Represents a node in the Tailscale network."""

    hostname: str
    node_id: str | None = None
    ip_addresses: list[str] = field(default_factory=list)
    tailnet_ip: str | None = None
    node_type: NodeType = NodeType.DEVICE
    status: NodeStatus = NodeStatus.PENDING
    authorized: bool = False
    last_seen: datetime | None = None
    created_at: datetime | None = None
    tags: list[str] = field(default_factory=list)
    advertised_routes: list[str] = field(default_factory=list)
    deployment_mode: DeploymentMode | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_online(self) -> bool:
        """Check if node is online."""
        return self.status == NodeStatus.ONLINE

    def is_authorized(self) -> bool:
        """Check if node is authorized to join the network."""
        return self.authorized and self.status not in (
            NodeStatus.UNAUTHORIZED,
            NodeStatus.EXPIRED,
        )


@dataclass
class TailscaleAuthKey:
    """Authentication key for registering nodes."""

    key: str
    key_id: str
    created_at: datetime
    expires_at: datetime | None = None
    reusable: bool = False
    ephemeral: bool = False
    preauthorized: bool = True
    tags: list[str] = field(default_factory=list)
    description: str | None = None

    def is_expired(self) -> bool:
        """Check if the auth key has expired."""
        if self.expires_at is None:
            return False
        return _utcnow() > self.expires_at


@dataclass
class TailnetConfig:
    """Configuration for a Tailscale tailnet."""

    tailnet: str  # Tailnet name (e.g., "example.com" or organization name)
    api_key: str | None = None
    oauth_client_id: str | None = None
    oauth_client_secret: str | None = None
    auth_key: str | None = None  # Pre-generated auth key for node registration
    default_tags: list[str] = field(default_factory=list)
    acl_policy: dict[str, Any] | None = None
    dns_enabled: bool = True
    magic_dns: bool = True
    exit_node_enabled: bool = False
    subnet_routes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TailscaleDeploymentConfig:
    """Configuration for deploying Tailscale on a node."""

    mode: DeploymentMode
    auth_key: str
    hostname: str | None = None
    advertise_exit_node: bool = False
    advertise_routes: list[str] = field(default_factory=list)
    accept_routes: bool = True
    accept_dns: bool = True
    shields_up: bool = False
    ssh: bool = False
    tags: list[str] = field(default_factory=list)
    extra_args: list[str] = field(default_factory=list)

    def to_tailscale_up_args(self) -> list[str]:
        """Generate arguments for 'tailscale up' command."""
        args = [f"--authkey={self.auth_key}"]

        if self.hostname:
            args.append(f"--hostname={self.hostname}")
        if self.advertise_exit_node:
            args.append("--advertise-exit-node")
        if self.advertise_routes:
            args.append(f"--advertise-routes={','.join(self.advertise_routes)}")
        if self.accept_routes:
            args.append("--accept-routes")
        if self.accept_dns:
            args.append("--accept-dns")
        if self.shields_up:
            args.append("--shields-up")
        if self.ssh:
            args.append("--ssh")
        if self.tags:
            args.append(f"--advertise-tags={','.join(self.tags)}")
        args.extend(self.extra_args)

        return args


@dataclass
class DeploymentResult:
    """Result of a Tailscale deployment operation."""

    success: bool
    node: TailscaleNode | None = None
    mode: DeploymentMode | None = None
    message: str = ""
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "DeploymentMode",
    "DeploymentResult",
    "NodeStatus",
    "NodeType",
    "TailnetConfig",
    "TailscaleAuthKey",
    "TailscaleDeploymentConfig",
    "TailscaleNode",
]
