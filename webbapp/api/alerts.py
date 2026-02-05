"""Alerts endpoint - provides recent alerts."""

from fastapi import APIRouter
from db import db

router = APIRouter()


@router.get("/api/alerts/recent")
async def get_recent_alerts(limit: int = 100) -> list[dict]:
    """Get recent alerts from database."""
    return db.fetch_alerts(limit=limit)


@router.post("/api/alerts/add")
async def add_alert(
    severity: int,
    signature: str,
    src_ip: str | None = None,
    dest_ip: str | None = None,
) -> dict:
    """Add a new alert (for testing)."""
    alert_id = db.insert_alert(severity, signature, src_ip, dest_ip)
    return {"id": alert_id, "status": "created"}
