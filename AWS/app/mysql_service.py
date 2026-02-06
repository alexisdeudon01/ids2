"""MySQL Service for database operations."""

import logging
from typing import Any, Optional
import mysql.connector
from mysql.connector import Error

logger = logging.getLogger(__name__)


class MySQLService:
    """MySQL database service wrapper."""

    def __init__(self, host: str, user: str, password: str, database: str, port: int = 3306):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.port = port
        self.connection: Optional[mysql.connector.MySQLConnection] = None

    def connect(self) -> bool:
        """Connect to MySQL database."""
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database
            )
            logger.info(f"Connected to MySQL: {self.host}:{self.port}/{self.database}")
            return True
        except Error as e:
            logger.error(f"MySQL connection failed: {e}")
            return False

    def disconnect(self):
        """Close MySQL connection."""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logger.info("MySQL connection closed")

    def execute_query(self, query: str, params: tuple = None) -> list[dict]:
        """Execute SELECT query and return results."""
        if not self.connection or not self.connection.is_connected():
            raise ConnectionError("Not connected to MySQL")

        try:
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(query, params or ())
            results = cursor.fetchall()
            cursor.close()
            logger.info(f"Query executed: {query[:100]}...")
            return results
        except Error as e:
            logger.error(f"Query execution failed: {e}")
            raise

    def execute_update(self, query: str, params: tuple = None) -> int:
        """Execute INSERT/UPDATE/DELETE query."""
        if not self.connection or not self.connection.is_connected():
            raise ConnectionError("Not connected to MySQL")

        try:
            cursor = self.connection.cursor()
            cursor.execute(query, params or ())
            self.connection.commit()
            affected_rows = cursor.rowcount
            cursor.close()
            logger.info(f"Update executed: {affected_rows} rows affected")
            return affected_rows
        except Error as e:
            self.connection.rollback()
            logger.error(f"Update execution failed: {e}")
            raise

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
