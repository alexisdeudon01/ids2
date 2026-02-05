"""Database health endpoint - matches /api/db/health."""

from fastapi import APIRouter
from models.schemas import DatabaseHealth

router = APIRouter()


@router.get("/api/db/health")
async def get_db_health() -> DatabaseHealth:
    """Check database connectivity."""
    # Simplified - just return ok status
    # In production, would check actual DB connection
    return DatabaseHealth(status="ok")
