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
                    mirror_interface TEXT,
                    ssh_key_path TEXT
                )
            """)
            
            # EC2 instances table for tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ec2_instances (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    instance_id TEXT UNIQUE NOT NULL,
                    region TEXT NOT NULL,
                    instance_type TEXT,
                    public_ip TEXT,
                    private_ip TEXT,
                    state TEXT,
                    elk_deployed INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
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
        ssh_key_path: str = "",
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
                    mirror_interface,
                    ssh_key_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    ssh_key_path,
                ),
            )
    
    def get_latest_deployment_config(self) -> dict | None:
        """Get the most recent deployment configuration."""
        with self.locked_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT aws_region, elk_ip, elastic_password, pi_host, pi_user,
                       pi_password, sudo_password, remote_dir, mirror_interface, ssh_key_path
                FROM deployment_config
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "aws_region": row[0],
                "elk_ip": row[1],
                "elastic_password": row[2],
                "pi_host": row[3],
                "pi_user": row[4],
                "pi_password": row[5],
                "sudo_password": row[6],
                "remote_dir": row[7],
                "mirror_interface": row[8],
                "ssh_key_path": row[9],
            }
    
    def upsert_ec2_instance(
        self,
        instance_id: str,
        region: str,
        instance_type: str = "",
        public_ip: str = "",
        private_ip: str = "",
        state: str = "",
        elk_deployed: bool = False,
    ) -> None:
        """Insert or update EC2 instance information."""
        with self.locked_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO ec2_instances (
                    instance_id, region, instance_type, public_ip, private_ip, state, elk_deployed, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(instance_id) DO UPDATE SET
                    region=excluded.region,
                    instance_type=excluded.instance_type,
                    public_ip=excluded.public_ip,
                    private_ip=excluded.private_ip,
                    state=excluded.state,
                    elk_deployed=excluded.elk_deployed,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (instance_id, region, instance_type, public_ip, private_ip, state, 1 if elk_deployed else 0),
            )
    
    def get_ec2_instances(self) -> list[dict]:
        """Get all tracked EC2 instances."""
        with self.locked_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT instance_id, region, instance_type, public_ip, private_ip, state, elk_deployed, created_at, updated_at
                FROM ec2_instances
                ORDER BY updated_at DESC
                """
            )
            rows = cursor.fetchall()
        return [
            {
                "instance_id": row[0],
                "region": row[1],
                "instance_type": row[2],
                "public_ip": row[3],
                "private_ip": row[4],
                "state": row[5],
                "elk_deployed": bool(row[6]),
                "created_at": row[7],
                "updated_at": row[8],
            }
            for row in rows
        ]
    
    def delete_ec2_instance(self, instance_id: str) -> None:
        """Delete EC2 instance from tracking."""
        with self.locked_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM ec2_instances WHERE instance_id = ?", (instance_id,))
    
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
