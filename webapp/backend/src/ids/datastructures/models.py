"""
Data models for the IDS platform.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AlertEvent(BaseModel):
    """Suricata alert event from EVE log."""

    timestamp: datetime
    event_type: str = Field(alias="event_type")
    src_ip: str | None = Field(None, alias="src_ip")
    dest_ip: str | None = Field(None, alias="dest_ip")
    alert: dict[str, Any] | None = None
    severity: int = 0
    signature: str = ""


class ElasticsearchHealth(BaseModel):
    """Elasticsearch cluster health status."""

    status: str  # green, yellow, red
    cluster_name: str
    number_of_nodes: int
    number_of_data_nodes: int
    active_primary_shards: int
    active_shards: int
    relocating_shards: int
    initializing_shards: int
    unassigned_shards: int
    daily_indices_count: int


class NetworkStats(BaseModel):
    """Network interface statistics."""

    interface: str
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    errin: int
    errout: int
    dropin: int
    dropout: int
    bitrate_sent: float  # bits per second
    bitrate_recv: float  # bits per second
    timestamp: datetime


class SystemHealth(BaseModel):
    """Raspberry Pi system health metrics."""

    cpu_percent: float
    memory_percent: float
    memory_used: int  # bytes
    memory_total: int  # bytes
    disk_percent: float
    disk_used: int  # bytes
    disk_total: int  # bytes
    temperature: float | None = None  # CPU temperature in Celsius
    uptime: float  # seconds
    timestamp: datetime


class PipelineStatus(BaseModel):
    """Pipeline component status."""

    interface: str  # eth0
    suricata: str  # running, stopped, error
    vector: str  # running, stopped, error
    elasticsearch: str  # green, yellow, red, unavailable
    timestamp: datetime


class AIHealingResponse(BaseModel):
    """AI healing suggestion response."""

    error_type: str
    error_message: str
    suggestion: str
    commands: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    timestamp: datetime


class TailscaleNode(BaseModel):
    """Tailscale node information."""

    name: str
    ip: str
    online: bool
    last_seen: datetime | None = None
    tags: list[str] = Field(default_factory=list)


class MirrorStatus(BaseModel):
    """Port mirroring verification status."""

    configured: bool
    active: bool
    source_port: str | None = None
    mirror_port: str | None = None
    message: str | None = None
    status_code: int | None = None
    checked_at: datetime | None = None
