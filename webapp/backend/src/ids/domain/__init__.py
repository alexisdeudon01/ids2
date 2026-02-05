"""
Domain - Entités de données structurées (Data-Oriented Design).

Définit les modèles de données immuables qui représentent le domaine métier.
Utilise dataclasses pour la clarté et la performance.
"""

# Import depuis les modules séparés
from .alerte import AlerteIDS, SeveriteAlerte, TypeAlerte
from .configuration import ConfigurationIDS
from .dashboard_models import (
    AIHealingResponse,
    AlertEvent,
    ElasticsearchHealth,
    MirrorStatus,
    NetworkStats,
    PipelineStatus,
    SystemHealth,
    TailscaleNode,
)
from .exceptions import (
    AlerteSourceIndisponible,
    ErreurAWS,
    ErreurConfiguration,
    ErreurIDS,
    ErreurSuricata,
)
from .metriques import ConditionSante, MetriquesSystem
from .tailscale import (
    DeploymentMode,
    DeploymentResult,
    NodeStatus,
    NodeType,
    TailnetConfig,
    TailscaleAuthKey,
    TailscaleDeploymentConfig,
    TailscaleNode,
)

__all__ = [
    "AIHealingResponse",
    "AlertEvent",
    "AlerteIDS",
    "AlerteSourceIndisponible",
    "ConditionSante",
    "ConfigurationIDS",
    # Tailscale domain models
    "DeploymentMode",
    "DeploymentResult",
    "ElasticsearchHealth",
    "ErreurAWS",
    "ErreurConfiguration",
    "ErreurIDS",
    "ErreurSuricata",
    "MetriquesSystem",
    "MirrorStatus",
    "NetworkStats",
    "NodeStatus",
    "NodeType",
    "PipelineStatus",
    "SeveriteAlerte",
    "SystemHealth",
    "TailnetConfig",
    "TailscaleAuthKey",
    "TailscaleDeploymentConfig",
    "TailscaleNode",
    "TypeAlerte",
]
