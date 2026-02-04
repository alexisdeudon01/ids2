"""
Shared data structures for the IDS application.
"""

from .models import (
    AIHealingResponse,
    AlertEvent,
    ElasticsearchHealth,
    MirrorStatus,
    NetworkStats,
    PipelineStatus,
    SystemHealth,
    TailscaleNode,
)

__all__ = [
    "AIHealingResponse",
    "AlertEvent",
    "ElasticsearchHealth",
    "MirrorStatus",
    "NetworkStats",
    "PipelineStatus",
    "SystemHealth",
    "TailscaleNode",
]
