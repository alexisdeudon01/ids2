"""Pipeline status endpoint."""

import subprocess
from datetime import datetime
from fastapi import APIRouter
from models.schemas import PipelineStatus

router = APIRouter()


def check_service_status(service: str) -> str:
    """Check systemd service status."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return "running" if result.returncode == 0 else "stopped"
    except Exception:
        return "unknown"


@router.get("/api/pipeline/status")
async def get_pipeline_status() -> PipelineStatus:
    """Get pipeline component status."""
    return PipelineStatus(
        interface="eth0",
        suricata=check_service_status("suricata"),
        vector=check_service_status("vector"),
        elasticsearch="green",  # Simplified
        timestamp=datetime.now().isoformat(),
    )
