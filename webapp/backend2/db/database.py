"""Simple SQLite database for IDS dashboard."""

import sqlite3
from pathlib import Path
from datetime import datetime


class Database:
    """Simple SQLite database wrapper."""
    
    def __init__(self, db_path: str = "db/ids.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self.init_db()
    
    def get_connection(self):
        """Get database connection."""
        return sqlite3.connect(self.db_path)
    
    def init_db(self):
        """Initialize database schema."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Alerts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                severity INTEGER NOT NULL,
                signature TEXT NOT NULL,
                src_ip TEXT,
                dest_ip TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # System metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                cpu_percent REAL,
                memory_percent REAL,
                disk_percent REAL,
                temperature REAL
            )
        """)
        
        conn.commit()
        conn.close()
    
    def check_health(self) -> bool:
        """Check database health."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
            return True
        except Exception:
            return False


# Global database instance
db = Database()
