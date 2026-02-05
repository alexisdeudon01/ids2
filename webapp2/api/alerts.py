"""Alerts endpoint - provides recent alerts."""

from fastapi import APIRouter
from datetime import datetime
from db import db

router = APIRouter()


@router.get("/api/alerts/recent")
async def get_recent_alerts(limit: int = 100) -> list[dict]:
    """Get recent alerts from database."""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT timestamp, severity, signature, src_ip, dest_ip
        FROM alerts
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,))
    
    alerts = []
    for row in cursor.fetchall():
        alerts.append({
            "timestamp": row[0],
            "severity": row[1],
            "signature": row[2],
            "src_ip": row[3],
            "dest_ip": row[4],
        })
    
    conn.close()
    return alerts


@router.post("/api/alerts/add")
async def add_alert(
    severity: int,
    signature: str,
    src_ip: str | None = None,
    dest_ip: str | None = None,
) -> dict:
    """Add a new alert (for testing)."""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    timestamp = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO alerts (timestamp, severity, signature, src_ip, dest_ip)
        VALUES (?, ?, ?, ?, ?)
    """, (timestamp, severity, signature, src_ip, dest_ip))
    
    conn.commit()
    alert_id = cursor.lastrowid
    conn.close()
    
    return {"id": alert_id, "status": "created"}
