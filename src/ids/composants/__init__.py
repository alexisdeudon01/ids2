"""Composants - implementations des services internes."""

from .base import BaseComponent
from .connectivity import ConnectivityTester
from .docker_manager import DockerManager
from .metrics_server import MetricsCollector, MetricsServer
from .resource_controller import ResourceController
from .vector_manager import VectorManager

# Import from new SOLID tailscale module for backward compatibility
from ..tailscale import DeviceState, NetworkSnapshot, TailnetMonitor

# Backward-compatible alias
ConnectivityChecker = ConnectivityTester

__all__ = [
    "BaseComponent",
    "ConnectivityTester",
    "ConnectivityChecker",
    "DeviceState",
    "DockerManager",
    "MetricsCollector",
    "MetricsServer",
    "NetworkSnapshot",
    "ResourceController",
    "TailnetMonitor",
    "VectorManager",
]
