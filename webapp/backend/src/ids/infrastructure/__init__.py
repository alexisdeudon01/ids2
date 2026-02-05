"""
Infrastructure modules for IDS project.

This package contains:
- DependencyManager: Manages Python and Docker dependencies
- DockerOrchestrator: Manages Docker builds and services
- SecretManager: Manages secrets in database
- AWSOpenSearchManager: AWS OpenSearch client
- RedisClient: Redis client
- InMemoryAlertStore: In-memory alert storage
- OpenSearchDomainManager: OpenSearch domain management
- RaspberryPiManager: Raspberry Pi management
- TailscaleManager: Tailscale network management
"""

from .alert_store import InMemoryAlertStore
from .aws_manager import AWSOpenSearchManager
from .dependency_manager import DependencyManager, dependency_manager
from .docker_orchestrator import DockerOrchestrator, docker_orchestrator
from .opensearch_manager import (
    OpenSearchDomainManager,
    OpenSearchDomainStatus,
    OpenSearchIndex,
)
from .raspberry_pi_manager import (
    DockerContainerStatus,
    RaspberryPiInfo,
    RaspberryPiManager,
    ServiceStatus,
)
from .redis_client import RedisClient
from .secret_manager import SecretManager, secret_manager
from .tailscale_manager import (
    TailscaleDevice,
    TailscaleKey,
    TailscaleManager,
    connect_to_tailnet,
    ensure_device_online,
)

__all__ = [
    "AWSOpenSearchManager",
    "DependencyManager",
    "DockerContainerStatus",
    "DockerOrchestrator",
    "InMemoryAlertStore",
    "OpenSearchDomainManager",
    "OpenSearchDomainStatus",
    "OpenSearchIndex",
    "RaspberryPiInfo",
    "RaspberryPiManager",
    "RedisClient",
    "SecretManager",
    "ServiceStatus",
    "TailscaleDevice",
    "TailscaleKey",
    "TailscaleManager",
    "connect_to_tailnet",
    "dependency_manager",
    "docker_orchestrator",
    "ensure_device_online",
    "secret_manager",
]