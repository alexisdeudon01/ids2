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
