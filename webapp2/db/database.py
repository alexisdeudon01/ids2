"""Simple SQLite database for IDS dashboard."""

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime


class Database:
    """Simple SQLite database wrapper."""
    
    def __init__(self, db_path: str = "db/ids.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._lock = threading.Lock()
        self.init_db()
    
    def get_connection(self):
        """Get database connection."""
        return sqlite3.connect(self.db_path, check_same_thread=False, timeout=30)

    @contextmanager
    def locked_connection(self):
        """Provide a thread-safe connection guarded by a lock."""
        with self._lock:
            conn = self.get_connection()
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()
    
    def init_db(self):
        """Initialize database schema."""
        with self.locked_connection() as conn:
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
        with self.locked_connection() as conn:
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
    
    def check_health(self) -> bool:
        """Check database health."""
        try:
            with self.locked_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False

    def fetch_alerts(self, limit: int = 100) -> list[dict]:
        """Fetch recent alerts in a thread-safe way."""
        with self.locked_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT timestamp, severity, signature, src_ip, dest_ip
                FROM alerts
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
        return [
            {
                "timestamp": row[0],
                "severity": row[1],
                "signature": row[2],
                "src_ip": row[3],
                "dest_ip": row[4],
            }
            for row in rows
        ]

    def insert_alert(
        self,
        severity: int,
        signature: str,
        src_ip: str | None = None,
        dest_ip: str | None = None,
    ) -> int:
        """Insert an alert and return its id."""
        timestamp = datetime.now().isoformat()
        with self.locked_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO alerts (timestamp, severity, signature, src_ip, dest_ip)
                VALUES (?, ?, ?, ?, ?)
                """,
                (timestamp, severity, signature, src_ip, dest_ip),
            )
            alert_id = cursor.lastrowid
        return int(alert_id)


# Global database instance
db = Database()
