from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class SuricataConfig:
    """Configuration spécifique à Suricata."""

    log_path: str = "/var/log/suricata/eve.json"
    rules_path: str = "/etc/suricata/rules"
    enabled: bool = True


@dataclass
class DockerConfig:
    """Configuration spécifique à Docker."""

    container_name: str = "suricata-container"
    image_name: str = "suricata/suricata"
    enabled: bool = False


@dataclass
class ConfigurationIDS:
    """Configuration globale du système IDS."""

    environnement: str = "dev"
    log_level: str = "INFO"
    suricata: SuricataConfig = field(default_factory=SuricataConfig)
    docker: DockerConfig = field(default_factory=DockerConfig)
    # Ajoutez d'autres configurations si nécessaire
    autres_parametres: Dict[str, Any] = field(default_factory=dict)
