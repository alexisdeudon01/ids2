"""
Abstract Interfaces (Protocols) for Tailscale Monitoring.

Dependency Inversion Principle: High-level modules depend on abstractions.
Interface Segregation Principle: Focused, minimal interfaces.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional, Protocol, runtime_checkable

from .models import DeviceState, NetworkSnapshot


@runtime_checkable
class TailscaleAPIClient(Protocol):
    """
    Protocol for Tailscale API clients.

    Interface Segregation: Only defines device fetching capability.
    """

    async def get_devices(self) -> List[DeviceState]:
        """Fetch all devices from the Tailscale API."""
        ...


@runtime_checkable
class ConnectivityTester(Protocol):
    """
    Protocol for testing network connectivity.

    Interface Segregation: Only defines ping capability.
    """

    def ping(self, ip: str, count: int = 3) -> Optional[float]:
        """
        Ping a device and return latency in milliseconds.

        Returns None if unreachable.
        """
        ...


@runtime_checkable
class NetworkVisualizer(Protocol):
    """
    Protocol for network visualization.

    Interface Segregation: Only defines visualization capability.
    """

    def generate(self, snapshot: NetworkSnapshot, output_path: str) -> str:
        """
        Generate a visualization of the network.

        Returns path to the generated file.
        """
        ...


class BaseAPIClient(ABC):
    """
    Abstract base class for Tailscale API clients.

    Open/Closed: Can be extended for different implementations
    (sync, async, mock, etc.)
    """

    def __init__(self, tailnet: str, api_key: str):
        self.tailnet = tailnet
        self._api_key = api_key  # Protected, never exposed

    @abstractmethod
    async def get_devices(self) -> List[DeviceState]:
        """Fetch all devices from the Tailscale API."""
        pass


class BaseConnectivityTester(ABC):
    """
    Abstract base class for connectivity testing.

    Open/Closed: Can be extended for different ping implementations
    (CLI, ICMP, mock, etc.)
    """

    @abstractmethod
    def ping(self, ip: str, count: int = 3) -> Optional[float]:
        """Ping a device and return latency."""
        pass

    def ping_all(self, devices: List[DeviceState]) -> None:
        """Ping all online devices and update their latency."""
        for device in devices:
            if device.is_online and device.tailscale_ip:
                device.latency_ms = self.ping(device.tailscale_ip)


class BaseVisualizer(ABC):
    """
    Abstract base class for network visualization.

    Open/Closed: Can be extended for different visualization formats
    (Pyvis, D3.js, Graphviz, etc.)
    """

    @abstractmethod
    def generate(self, snapshot: NetworkSnapshot, output_path: str) -> str:
        """Generate visualization and return file path."""
        pass
