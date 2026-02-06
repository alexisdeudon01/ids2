"""Unified SSH client - eliminates all SSH duplicates."""

import io
import json
import logging
import os
import posixpath
import shlex
import uuid
from pathlib import Path
from typing import Callable, Optional
import paramiko

logger = logging.getLogger(__name__)


class UnifiedSSHClient:
    """Unified SSH client combining all SSH functionality."""

    def __init__(
        self,
        host: str,
        user: str,
        password: str = "",
        key_path: str = "",
        sudo_password: str = "",
        port: int = 22,
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        self.host = host
        self.user = user
        self.password = password
        self.key_path = key_path
        self.sudo_password = sudo_password
        self.port = port
        self._log = log_callback or logger.info
        self.client: Optional[paramiko.SSHClient] = None
        self.sftp: Optional[paramiko.SFTPClient] = None
        self._connected = False

    def connect(self) -> bool:
        """Establish SSH connection."""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            key_filename = os.path.expanduser(self.key_path) if self.key_path else None
            if key_filename and not Path(key_filename).is_file():
                key_filename = None
            
            password_value = self.password or None
            
            self._log(f"Connecting to {self.user}@{self.host}:{self.port}...")
            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.user,
                password=password_value,
                key_filename=key_filename,
                allow_agent=True,
                look_for_keys=True,
                timeout=20,
            )
            self.sftp = self.client.open_sftp()
            self._connected = True
            self._log("SSH connection established")
            return True
        except Exception as e:
            self._log(f"SSH connection failed: {e}")
            self._connected = False
            return False

    def disconnect(self):
        """Close SSH connection."""
        if self.sftp:
            self.sftp.close()
        if self.client:
            self.client.close()
        self._connected = False
        self._log("SSH connection closed")

    def execute(self, command: str, sudo: bool = False, check: bool = True, verbose: bool = True) -> tuple[int, str, str]:
        """Execute command on remote host."""
        if not self._connected:
            raise ConnectionError("Not connected. Call connect() first.")

        wrapped = f"bash -lc {json.dumps(command)}"
        if sudo:
            wrapped = f"sudo -S -p '' {wrapped}"

        if verbose:
            self._log(f"Executing: {command}")

        stdin, stdout, stderr = self.client.exec_command(wrapped)
        
        if sudo and self.sudo_password:
            stdin.write(self.sudo_password + "\\n")
            stdin.flush()

        out_lines = []
        err_lines = []
        
        for line in iter(stdout.readline, ""):
            if line:
                out_lines.append(line)
                if verbose:
                    self._log(line.rstrip())
        
        for line in iter(stderr.readline, ""):
            if line:
                err_lines.append(line)
                if verbose:
                    self._log(line.rstrip())

        exit_code = stdout.channel.recv_exit_status()
        
        if verbose:
            self._log(f"Exit code: {exit_code}")

        if check and exit_code != 0:
            raise RuntimeError(f"Remote command failed ({exit_code}): {command}")

        return exit_code, "".join(out_lines), "".join(err_lines)

    def upload_file(self, local_path: str, remote_path: str, verbose: bool = True) -> bool:
        """Upload file to remote host."""
        if not self._connected:
            raise ConnectionError("Not connected. Call connect() first.")

        try:
            if verbose:
                self._log(f"Uploading {local_path} -> {remote_path}")
            
            self.sftp.put(local_path, remote_path)
            
            if verbose:
                self._log("Upload completed")
            return True
        except Exception as e:
            self._log(f"Upload failed: {e}")
            return False

    def upload_directory(self, local_dir: Path, remote_dir: str, verbose: bool = True) -> bool:
        """Upload directory to remote host."""
        if not self._connected:
            raise ConnectionError("Not connected. Call connect() first.")

        ignore_dirs = {".venv", "__pycache__", "node_modules", ".git", "dist"}
        ignore_files = {"ids.db", "*.pyc"}

        try:
            if verbose:
                self._log(f"Uploading directory {local_dir} -> {remote_dir}")

            for root, dirs, files in os.walk(local_dir):
                dirs[:] = [d for d in dirs if d not in ignore_dirs]
                rel_path = Path(root).relative_to(local_dir)
                remote_path = posixpath.join(remote_dir, str(rel_path))
                self.execute(f"mkdir -p '{remote_path}'", sudo=False, verbose=False)

                for name in files:
                    if name in ignore_files or name.endswith(".pyc"):
                        continue
                    local_file = Path(root) / name
                    remote_file = posixpath.join(remote_path, name)
                    self.sftp.put(str(local_file), remote_file)

            if verbose:
                self._log("Directory upload completed")
            return True
        except Exception as e:
            self._log(f"Directory upload failed: {e}")
            return False

    def write_file(self, remote_path: str, content: str, sudo: bool = False) -> None:
        """Write content to remote file."""
        tmp_path = f"/tmp/{uuid.uuid4().hex}.tmp"
        with io.BytesIO(content.encode("utf-8")) as buff:
            self.sftp.putfo(buff, tmp_path)
        self.execute(f"mv '{tmp_path}' '{remote_path}'", sudo=sudo)

    def exists(self, remote_path: str) -> bool:
        """Check if remote file exists."""
        exit_code, _, _ = self.execute(f"test -f {shlex.quote(remote_path)}", check=False, verbose=False)
        return exit_code == 0

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
