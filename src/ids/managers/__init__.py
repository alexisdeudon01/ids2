"""
Gestionnaires pour l'infrastructure IDS.

Modules:
- tailscale_manager: Gestion du réseau Tailscale (devices, keys, ACLs)
- opensearch_manager: Gestion des domaines AWS OpenSearch
- raspberry_pi_manager: Gestion du Raspberry Pi (SSH, services, Docker)
"""

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
from .tailscale_manager import (
    TailscaleDevice,
    TailscaleKey,
    TailscaleManager,
    connect_to_tailnet,
    ensure_device_online,
)

__all__ = [
    # Tailscale
    "TailscaleManager",
    "TailscaleDevice",
    "TailscaleKey",
    "connect_to_tailnet",
    "ensure_device_online",
    # OpenSearch
    "OpenSearchDomainManager",
    "OpenSearchDomainStatus",
    "OpenSearchIndex",
    # Raspberry Pi
    "RaspberryPiManager",
    "RaspberryPiInfo",
    "ServiceStatus",
    "DockerContainerStatus",
]
