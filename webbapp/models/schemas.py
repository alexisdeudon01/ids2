"""Data models matching frontend requirements."""

from datetime import datetime
from pydantic import BaseModel


class SystemHealth(BaseModel):
    """System health metrics for frontend."""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    temperature: float | None = None


class DatabaseHealth(BaseModel):
    """Database health status."""
    status: str  # "ok" or "error"


class NetworkStats(BaseModel):
    """Network interface statistics."""
    interface: str
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    bitrate_sent: float
    bitrate_recv: float
    timestamp: str


class PipelineStatus(BaseModel):
    """Pipeline component status."""
    interface: str
    suricata: str
    vector: str
    elasticsearch: str
    timestamp: str
