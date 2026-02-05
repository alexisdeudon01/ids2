"""System health endpoint - matches /api/system/health."""

import psutil
from pathlib import Path
from fastapi import APIRouter
from models.schemas import SystemHealth

router = APIRouter()


@router.get("/api/system/health")
async def get_system_health() -> SystemHealth:
    """Get Raspberry Pi system health metrics."""
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    
    # Get CPU temperature (Raspberry Pi)
    temperature = None
    try:
        temp_file = Path("/sys/class/thermal/thermal_zone0/temp")
        if temp_file.exists():
            temp_raw = temp_file.read_text().strip()
            temperature = float(temp_raw) / 1000.0
    except Exception:
        pass
    
    return SystemHealth(
        cpu_percent=cpu_percent,
        memory_percent=memory.percent,
        disk_percent=disk.percent,
        temperature=temperature,
    )
