#!/usr/bin/env python3
from __future__ import annotations

import getpass
import json
import os
import posixpath
import sys
import time
from pathlib import Path
from typing import Any

try:
    import paramiko
except ImportError:
    print("❌ paramiko is required. Install with: pip install paramiko")
    sys.exit(1)


# `deploy.py` lives in `webapp/backend/`, so:
# - parents[0] = webapp/backend
# - parents[1] = webapp
# - parents[2] = repository root
#
# We need the repository root so `upload_repo()` places files under:
#   /opt/ids-dashboard/webapp/backend/...
# instead of:
#   /opt/ids-dashboard/backend/...
REPO_ROOT = Path(__file__).resolve().parents[2]
REMOTE_DIR = os.getenv("REMOTE_DIR", "/opt/ids-dashboard")
SERVICE_NAME = "ids-dashboard.service"


def prompt_value(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or (default or "")


def write_secret_file(payload: dict[str, str]) -> None:
    secret_path = REPO_ROOT / "secret.json"
    secret_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    # Set restrictive permissions (read/write for owner only)
    secret_path.chmod(0o600)


def connect_ssh(host: str, user: str, password: str, max_retries: int = 3) -> paramiko.SSHClient:
    """Connect to SSH with retry mechanism."""
    client = paramiko.SSHClient()
    # Warn user about auto-accepting host keys
    import warnings
    warnings.warn(
        "SSH host key verification is set to AutoAddPolicy. "
        "This automatically accepts unknown host keys. Use with caution.",
        UserWarning
    )
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            client.connect(hostname=host, username=user, password=password, timeout=10)
            return client
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                print(f"⚠️  SSH connection attempt {attempt}/{max_retries} failed, retrying...")
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise ConnectionError(f"Failed to connect to {user}@{host} after {max_retries} attempts: {e}") from last_error
    return client


def run_command(client: paramiko.SSHClient, command: str, sudo_password: str | None = None, check: bool = True) -> Any:
    """Run a command via SSH. Returns object with returncode, stdout, stderr attributes."""
    if sudo_password:
        command = f"sudo -S -p '' {command}"
    stdin, stdout, stderr = client.exec_command(command)
    if sudo_password:
        stdin.write(f"{sudo_password}\n")
        stdin.flush()
    exit_code = stdout.channel.recv_exit_status()
    stdout_text = stdout.read().decode("utf-8")
    stderr_text = stderr.read().decode("utf-8")
    
    # Create a CompletedProcess-like object
    class SSHResult:
        def __init__(self, returncode, stdout, stderr):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr
    
    result = SSHResult(exit_code, stdout_text, stderr_text)
    
    if exit_code != 0 and check:
        raise RuntimeError(f"Command failed: {command}\n{stderr_text}")
    
    return result


def upload_repo(client: paramiko.SSHClient, local_root: Path, remote_root: str) -> None:
    ignore_dir_names = {
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        ".venv",
        "venv",
    }
    sftp = client.open_sftp()
    try:
        for root, dirs, files in os.walk(local_root):
            rel = os.path.relpath(root, local_root)
            rel_parts = () if rel == "." else Path(rel).parts
            # Skip heavy / generated directories anywhere in the tree.
            if any(part in ignore_dir_names for part in rel_parts):
                dirs[:] = []
                continue
            # Prevent os.walk from descending into ignored directories.
            dirs[:] = [d for d in dirs if d not in ignore_dir_names]
            remote_path = posixpath.join(remote_root, rel) if rel != "." else remote_root
            try:
                sftp.mkdir(remote_path)
            except IOError:
                pass
            for file_name in files:
                if file_name == "secret.json":
                    continue
                local_file = Path(root) / file_name
                remote_file = posixpath.join(remote_path, file_name)
                sftp.put(local_file.as_posix(), remote_file)
    finally:
        sftp.close()


def main() -> int:
    print("=== Déploiement Dashboard IDS ===")
    host = prompt_value("IP du Raspberry Pi")
    user = prompt_value("Utilisateur SSH", "pi")
    ssh_password = getpass.getpass("Mot de passe SSH: ")
    sudo_password = getpass.getpass("Mot de passe sudo: ")

    if not host:
        print("IP du Raspberry Pi requise.")
        return 1

    write_secret_file(
        {
            "pi_ssh_user": user,
            "pi_ssh_password": ssh_password,
            "pi_sudo_password": sudo_password,
        }
    )

    print("Vérification de la connectivité...")
    client = None
    deployment_steps = []  # Track deployment steps for rollback
    
    try:
        client = connect_ssh(host, user, ssh_password)
        print("✅ Connexion SSH réussie")
        
        # Check if python3 exists on remote system
        check_python = run_command(client, "command -v python3", sudo_password=None, check=False)
        if check_python.returncode != 0:
            print("❌ python3 not found on remote system. Please install Python 3 first.")
            return 1
        
        # Check remote directory permissions
        check_dir = run_command(client, f"test -w {REMOTE_DIR} || (mkdir -p {REMOTE_DIR} && chown -R {user}:{user} {REMOTE_DIR})", sudo_password=sudo_password, check=False)
        if check_dir.returncode != 0:
            print(f"⚠️  Warning: Could not ensure write permissions on {REMOTE_DIR}")
        
        deployment_steps.append("ssh_connected")
        run_command(client, f"mkdir -p {REMOTE_DIR}", sudo_password=sudo_password)
        deployment_steps.append("dir_created")

        print("Upload du code...")
        upload_repo(client, REPO_ROOT, REMOTE_DIR)
        print("✅ Code uploadé")
        deployment_steps.append("code_uploaded")

        print("Installation des dépendances...")
        req_file = REPO_ROOT / "webapp" / "backend" / "requirements.txt"
        if not req_file.exists():
            print(f"❌ requirements.txt not found at {req_file}")
            return 1
        run_command(
            client,
            f"cd {REMOTE_DIR}/webapp/backend && python3 -m pip install -r requirements.txt",
            sudo_password=sudo_password,
        )
        deployment_steps.append("deps_installed")

        print("Configuration du service systemd...")
        service_file = REPO_ROOT / "webapp" / "backend" / "deploy" / SERVICE_NAME
        if not service_file.exists():
            print(f"❌ Service file not found at {service_file}")
            return 1
        
        run_command(
            client,
            f"cp {REMOTE_DIR}/webapp/backend/deploy/{SERVICE_NAME} /etc/systemd/system/{SERVICE_NAME}",
            sudo_password=sudo_password,
        )
        deployment_steps.append("service_installed")
        run_command(client, "systemctl daemon-reload", sudo_password=sudo_password)
        run_command(client, f"systemctl enable {SERVICE_NAME}", sudo_password=sudo_password)
        print("✅ Service configuré")
        deployment_steps.append("service_enabled")
        
        print("Démarrage du dashboard...")
        run_command(client, f"systemctl restart {SERVICE_NAME}", sudo_password=sudo_password)
        print("✅ Dashboard démarré")

        print(f"✅ Dashboard accessible sur http://{host}:8080")
        print("=== Déploiement terminé avec succès ===")
        return 0
        
    except Exception as e:
        print(f"❌ Deployment failed: {e}")
        # Rollback: remove service if it was installed
        if client and "service_installed" in deployment_steps:
            try:
                print("🔄 Rolling back: removing service...")
                run_command(client, f"systemctl disable {SERVICE_NAME} || true", sudo_password=sudo_password, check=False)
                run_command(client, f"rm -f /etc/systemd/system/{SERVICE_NAME}", sudo_password=sudo_password, check=False)
                run_command(client, "systemctl daemon-reload", sudo_password=sudo_password, check=False)
            except Exception as rollback_error:
                print(f"⚠️  Rollback warning: {rollback_error}")
        return 1
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
