"""
Configuration systeme IDS.

Contient les parametres globaux de l'agent.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ConfigurationIDS:
    """Configuration systeme immuable."""

    version: str = "2.0.0"
    interface_reseau: str = "eth0"
    repertoire_logs: str = "/mnt/ram_logs"
    repertoire_config: str = "config/"

    # Suricata
    suricata_config_path: str = "suricata/suricata.yaml"
    suricata_rules_path: str = "suricata/rules/"
    suricata_log_path: str = "/mnt/ram_logs/eve.json"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # AWS OpenSearch
    aws_region: str = "eu-west-1"
    aws_opensearch_domain: str = "ids-opensearch"
    aws_opensearch_endpoint: str | None = None

    # Docker
    docker_compose_path: str = "docker/docker-compose.yml"

    # Ressources
    cpu_limit_percent: float = 80.0
    ram_limit_percent: float = 85.0
    throttling_enabled: bool = True

    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "ConfigurationIDS",
]
