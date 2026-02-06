"""SSH client for remote Pi operations."""

from __future__ import annotations

import io
import json
import os
import posixpath
import uuid
from pathlib import Path
from typing import Callable

import paramiko


def _tqdm(iterable, **kwargs):
    try:
        from tqdm import tqdm  # type: ignore
        return tqdm(iterable, **kwargs)
    except Exception:
        return iterable


class SSHClient:
    """SSH client with SFTP support."""
    
    def __init__(
        self,
        host: str,
        user: str,
        password: str,
        sudo_password: str,
        log_callback: Callable[[str], None],
        ssh_key_path: str = "",
    ) -> None:
        self.host = host
        self.user = user
        self.password = password
        self.sudo_password = sudo_password
        self._log = log_callback
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        key_filename = os.path.expanduser(ssh_key_path) if ssh_key_path else None
        self.client.connect(
            hostname=host,
            username=user,
            password=password or None,
            key_filename=key_filename,
            allow_agent=True,
            look_for_keys=True,
            timeout=20,
        )
        self.sftp = self.client.open_sftp()

    def close(self) -> None:
        self.sftp.close()
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def _exec(self, command: str) -> tuple[int, str, str]:
        stdin, stdout, stderr = self.client.exec_command(command)
        if command.startswith("sudo -S"):
            stdin.write(self.sudo_password + "\n")
            stdin.flush()
        
        out_lines = []
        err_lines = []
        for line in iter(stdout.readline, ""):
            if line:
                out_lines.append(line)
                self._log(line.rstrip())
        for line in iter(stderr.readline, ""):
            if line:
                err_lines.append(line)
                self._log(line.rstrip())
        
        exit_status = stdout.channel.recv_exit_status()
        return exit_status, "".join(out_lines), "".join(err_lines)

    def run(self, command: str, sudo: bool = False, check: bool = True) -> None:
        wrapped = f"bash -lc {json.dumps(command)}"
        if sudo:
            wrapped = f"sudo -S -p '' {wrapped}"
        exit_status, _, _ = self._exec(wrapped)
        if check and exit_status != 0:
            raise RuntimeError(f"Remote command failed ({exit_status}): {command}")

    def write_file(self, remote_path: str, content: str, sudo: bool = False) -> None:
        tmp_path = f"/tmp/{uuid.uuid4().hex}.tmp"
        with io.BytesIO(content.encode("utf-8")) as buff:
            self.sftp.putfo(buff, tmp_path)
        self.run(f"mv '{tmp_path}' '{remote_path}'", sudo=sudo)

    def upload_directory(self, local_dir: Path, remote_dir: str) -> None:
        ignore_dirs = {".venv", "__pycache__", "node_modules", ".git"}
        ignore_files = {"ids.db"}

        upload_items: list[tuple[Path, str]] = []
        for root, dirs, files in os.walk(local_dir):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            rel_path = Path(root).relative_to(local_dir)
            remote_path = posixpath.join(remote_dir, str(rel_path))
            self.run(f"mkdir -p '{remote_path}'", sudo=False)

            for name in files:
                if name in ignore_files:
                    continue
                local_file = Path(root) / name
                remote_file = posixpath.join(remote_path, name)
                upload_items.append((local_file, remote_file))

        for local_file, remote_file in _tqdm(upload_items, desc="Uploading webapp files", unit="file"):
            self.sftp.put(str(local_file), remote_file)
