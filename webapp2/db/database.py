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

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deployment_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                aws_region TEXT,
                elk_ip TEXT,
                elastic_password TEXT,
                pi_host TEXT,
                pi_user TEXT,
                pi_password TEXT,
                sudo_password TEXT,
                remote_dir TEXT,
                mirror_interface TEXT
            )
        """)
        
        conn.commit()
        conn.close()

    def save_deployment_config(
        self,
        aws_region: str,
        elk_ip: str,
        elastic_password: str,
        pi_host: str,
        pi_user: str,
        pi_password: str,
        sudo_password: str,
        remote_dir: str,
        mirror_interface: str,
    ) -> None:
        """Persist deployment configuration to the database."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO deployment_config (
                aws_region,
                elk_ip,
                elastic_password,
                pi_host,
                pi_user,
                pi_password,
                sudo_password,
                remote_dir,
                mirror_interface
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                aws_region,
                elk_ip,
                elastic_password,
                pi_host,
                pi_user,
                pi_password,
                sudo_password,
                remote_dir,
                mirror_interface,
            ),
        )
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
