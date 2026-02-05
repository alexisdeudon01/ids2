"""Database health endpoint - matches /api/db/health."""

from fastapi import APIRouter
from models.schemas import DatabaseHealth
from db import db

router = APIRouter()


@router.get("/api/db/health")
async def get_db_health() -> DatabaseHealth:
    """Check database connectivity."""
    is_healthy = db.check_health()
    return DatabaseHealth(status="ok" if is_healthy else "error")
