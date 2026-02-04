"""
Data Models for Tailscale Network Monitoring.

Single Responsibility: Only contains data structures, no business logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class DeviceState:
    """
    Represents the state of a single Tailscale device.

    Immutable data structure capturing a point-in-time device state.
    """

    device_id: str
    hostname: str
    tailscale_ip: str
    os: str
    status: str  # "online" or "offline"
    last_seen: str
    tags: List[str] = field(default_factory=list)
    latency_ms: Optional[float] = None
    authorized: bool = True
    client_version: str = ""

    @property
    def is_online(self) -> bool:
        """Check if device is online."""
        return self.status == "online"

    @property
    def is_reachable(self) -> bool:
        """Check if device is online and has valid latency."""
        return self.is_online and self.latency_ms is not None and self.latency_ms >= 0

    @property
    def console_url(self) -> str:
        """URL to device in Tailscale Admin Console."""
        return f"https://login.tailscale.com/admin/machines/{self.device_id}"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "device_id": self.device_id,
            "hostname": self.hostname,
            "tailscale_ip": self.tailscale_ip,
            "os": self.os,
            "status": self.status,
            "last_seen": self.last_seen,
            "tags": self.tags,
            "latency_ms": self.latency_ms,
            "authorized": self.authorized,
            "console_url": self.console_url,
        }


@dataclass
class NetworkSnapshot:
    """
    Point-in-time snapshot of the entire Tailscale mesh network.

    Immutable aggregate of all device states at a specific moment.
    """

    timestamp: str
    tailnet: str
    devices: List[DeviceState] = field(default_factory=list)

    @property
    def total_nodes(self) -> int:
        """Total number of devices in the tailnet."""
        return len(self.devices)

    @property
    def online_nodes(self) -> int:
        """Number of online devices."""
        return sum(1 for d in self.devices if d.is_online)

    @property
    def offline_nodes(self) -> int:
        """Number of offline devices."""
        return self.total_nodes - self.online_nodes

    @property
    def reachable_nodes(self) -> int:
        """Number of devices that responded to ping."""
        return sum(1 for d in self.devices if d.is_reachable)

    @property
    def average_latency_ms(self) -> Optional[float]:
        """Average latency across all reachable devices."""
        latencies = [d.latency_ms for d in self.devices if d.is_reachable]
        return sum(latencies) / len(latencies) if latencies else None

    @property
    def min_latency_ms(self) -> Optional[float]:
        """Minimum latency across all reachable devices."""
        latencies = [d.latency_ms for d in self.devices if d.is_reachable]
        return min(latencies) if latencies else None

    @property
    def max_latency_ms(self) -> Optional[float]:
        """Maximum latency across all reachable devices."""
        latencies = [d.latency_ms for d in self.devices if d.is_reachable]
        return max(latencies) if latencies else None

    @property
    def availability_percent(self) -> float:
        """Percentage of devices that are online."""
        return (self.online_nodes / self.total_nodes * 100) if self.total_nodes > 0 else 0.0

    def get_device_by_ip(self, ip: str) -> Optional[DeviceState]:
        """Find a device by its Tailscale IP."""
        for device in self.devices:
            if device.tailscale_ip == ip:
                return device
        return None

    def get_device_by_hostname(self, hostname: str) -> Optional[DeviceState]:
        """Find a device by its hostname."""
        for device in self.devices:
            if device.hostname.lower() == hostname.lower():
                return device
        return None

    def get_online_devices(self) -> List[DeviceState]:
        """Return only online devices."""
        return [d for d in self.devices if d.is_online]

    def get_reachable_devices(self) -> List[DeviceState]:
        """Return only reachable devices (online with valid latency)."""
        return [d for d in self.devices if d.is_reachable]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize snapshot to dictionary."""
        return {
            "timestamp": self.timestamp,
            "tailnet": self.tailnet,
            "total_nodes": self.total_nodes,
            "online_nodes": self.online_nodes,
            "offline_nodes": self.offline_nodes,
            "reachable_nodes": self.reachable_nodes,
            "average_latency_ms": self.average_latency_ms,
            "min_latency_ms": self.min_latency_ms,
            "max_latency_ms": self.max_latency_ms,
            "availability_percent": self.availability_percent,
            "devices": [d.to_dict() for d in self.devices],
        }

    @classmethod
    def create(cls, tailnet: str, devices: List[DeviceState]) -> "NetworkSnapshot":
        """Factory method to create a snapshot with current timestamp."""
        return cls(
            timestamp=datetime.now().isoformat(),
            tailnet=tailnet,
            devices=devices,
        )


@dataclass
class HealthMetrics:
    """Network health metrics derived from a snapshot."""

    total_nodes: int
    online_nodes: int
    offline_nodes: int
    reachable_nodes: int
    unreachable_nodes: int
    availability_percent: float
    average_latency_ms: Optional[float]
    min_latency_ms: Optional[float]
    max_latency_ms: Optional[float]

    @classmethod
    def from_snapshot(cls, snapshot: NetworkSnapshot) -> "HealthMetrics":
        """Create health metrics from a network snapshot."""
        return cls(
            total_nodes=snapshot.total_nodes,
            online_nodes=snapshot.online_nodes,
            offline_nodes=snapshot.offline_nodes,
            reachable_nodes=snapshot.reachable_nodes,
            unreachable_nodes=snapshot.online_nodes - snapshot.reachable_nodes,
            availability_percent=snapshot.availability_percent,
            average_latency_ms=snapshot.average_latency_ms,
            min_latency_ms=snapshot.min_latency_ms,
            max_latency_ms=snapshot.max_latency_ms,
        )
