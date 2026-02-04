"""Composants - implementations des services internes."""

# Import from new SOLID tailscale module for backward compatibility
from ..tailscale import DeviceState, NetworkSnapshot, TailnetMonitor
from .base import BaseComponent
from .connectivity import ConnectivityTester
from .docker_manager import DockerManager
from .metrics_server import MetricsCollector, MetricsServer
from .resource_controller import ResourceController
from .vector_manager import VectorManager

# Backward-compatible alias
ConnectivityChecker = ConnectivityTester

__all__ = [
    "BaseComponent",
    "ConnectivityChecker",
    "ConnectivityTester",
    "DeviceState",
    "DockerManager",
    "MetricsCollector",
    "MetricsServer",
    "NetworkSnapshot",
    "ResourceController",
    "TailnetMonitor",
    "VectorManager",
]
