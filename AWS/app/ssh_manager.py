"""SSH Manager for remote deployment and command execution."""

import logging
from pathlib import Path
from typing import Optional
import paramiko
from scp import SCPClient

logger = logging.getLogger(__name__)


class SSHManager:
    """Manage SSH connections and remote operations."""

    def __init__(self, host: str, user: str, key_path: str, port: int = 22):
        self.host = host
        self.user = user
        self.key_path = key_path
        self.port = port
        self.client: Optional[paramiko.SSHClient] = None
        self._connected = False

    def connect(self) -> bool:
        """Establish SSH connection."""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            logger.info(f"Connecting to {self.user}@{self.host}:{self.port}...")
            self.client.connect(
                self.host,
                port=self.port,
                username=self.user,
                key_filename=self.key_path,
                timeout=10,
            )
            self._connected = True
            logger.info("SSH connection established")
            return True
        except Exception as e:
            logger.error(f"SSH connection failed: {e}")
            self._connected = False
            return False

    def disconnect(self):
        """Close SSH connection."""
        if self.client:
            self.client.close()
            self._connected = False
            logger.info("SSH connection closed")

    def execute(self, command: str, sudo: bool = False, verbose: bool = True) -> tuple[int, str, str]:
        """Execute command on remote host."""
        if not self._connected:
            raise ConnectionError("Not connected. Call connect() first.")

        if sudo:
            command = f"sudo {command}"

        if verbose:
            logger.info(f"Executing: {command}")

        stdin, stdout, stderr = self.client.exec_command(command)
        exit_code = stdout.channel.recv_exit_status()
        
        stdout_text = stdout.read().decode().strip()
        stderr_text = stderr.read().decode().strip()

        if verbose:
            if stdout_text:
                logger.info(f"STDOUT: {stdout_text}")
            if stderr_text:
                logger.warning(f"STDERR: {stderr_text}")
            logger.info(f"Exit code: {exit_code}")

        return exit_code, stdout_text, stderr_text

    def upload_file(self, local_path: str, remote_path: str, verbose: bool = True) -> bool:
        """Upload file to remote host."""
        if not self._connected:
            raise ConnectionError("Not connected. Call connect() first.")

        try:
            if verbose:
                logger.info(f"Uploading {local_path} -> {remote_path}")
            
            with SCPClient(self.client.get_transport()) as scp:
                scp.put(local_path, remote_path)
            
            if verbose:
                logger.info("Upload completed")
            return True
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return False

    def upload_directory(self, local_dir: str, remote_dir: str, verbose: bool = True) -> bool:
        """Upload directory to remote host."""
        if not self._connected:
            raise ConnectionError("Not connected. Call connect() first.")

        try:
            if verbose:
                logger.info(f"Uploading directory {local_dir} -> {remote_dir}")
            
            # Create remote directory
            self.execute(f"mkdir -p {remote_dir}", sudo=True, verbose=verbose)
            
            with SCPClient(self.client.get_transport()) as scp:
                scp.put(local_dir, remote_dir, recursive=True)
            
            if verbose:
                logger.info("Directory upload completed")
            return True
        except Exception as e:
            logger.error(f"Directory upload failed: {e}")
            return False

    def execute_test(self) -> str:
        """Test connection to remote host."""
        try:
            if not self._connected:
                self.connect()
            
            exit_code, stdout, stderr = self.execute("uptime", verbose=True)
            
            if exit_code == 0:
                return f"Success: {stdout}"
            else:
                return f"Failed: {stderr}"
        except Exception as e:
            return f"Failed: {str(e)}"
        finally:
            self.disconnect()

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
