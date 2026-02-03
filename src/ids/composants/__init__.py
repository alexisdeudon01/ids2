"""Composants - implementations des services internes."""

from .base import BaseComponent
from .connectivity import ConnectivityTester
from .docker_manager import DockerManager
from .metrics_server import MetricsCollector, MetricsServer
from .resource_controller import ResourceController
from .tailscale_manager import (
    TailscaleManager,
    DeploymentCapabilities,
    deployment_strategy,
    handles_node_type,
)
from .vector_manager import VectorManager

# Backward-compatible alias
ConnectivityChecker = ConnectivityTester

__all__ = [
    "BaseComponent",
    "ConnectivityTester",
    "ConnectivityChecker",
    "DockerManager",
    "MetricsCollector",
    "MetricsServer",
    "ResourceController",
    "TailscaleManager",
    "DeploymentCapabilities",
    "deployment_strategy",
    "handles_node_type",
    "VectorManager",
]
