#!/usr/bin/env python3
from __future__ import annotations

import getpass
import json
import os
import posixpath
import sys
from pathlib import Path

import paramiko


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
REMOTE_DIR = "/opt/ids-dashboard"
SERVICE_NAME = "ids-dashboard.service"


def prompt_value(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or (default or "")


def write_secret_file(payload: dict[str, str]) -> None:
    secret_path = REPO_ROOT / "secret.json"
    secret_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def connect_ssh(host: str, user: str, password: str) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, username=user, password=password, timeout=10)
    return client


def run_command(client: paramiko.SSHClient, command: str, sudo_password: str | None = None) -> None:
    if sudo_password:
        command = f"sudo -S -p '' {command}"
    stdin, stdout, stderr = client.exec_command(command)
    if sudo_password:
        stdin.write(f"{sudo_password}\n")
        stdin.flush()
    exit_code = stdout.channel.recv_exit_status()
    if exit_code != 0:
        error = stderr.read().decode("utf-8")
        raise RuntimeError(f"Command failed: {command}\n{error}")


def upload_repo(client: paramiko.SSHClient, local_root: Path, remote_root: str) -> None:
    ignore_dir_names = {
        "__pycache__",
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
    client = connect_ssh(host, user, ssh_password)
    try:
        print("✅ Connexion SSH réussie")
        run_command(client, f"mkdir -p {REMOTE_DIR}", sudo_password=sudo_password)

        print("Upload du code...")
        upload_repo(client, REPO_ROOT, REMOTE_DIR)
        print("✅ Code uploadé")

        print("Installation des dépendances...")
        run_command(
            client,
            f"cd {REMOTE_DIR}/webapp/backend && python3 -m pip install -r requirements.txt",
            sudo_password=sudo_password,
        )

        print("Configuration du service systemd...")
        run_command(
            client,
            f"cp {REMOTE_DIR}/service/{SERVICE_NAME} /etc/systemd/system/{SERVICE_NAME}",
            sudo_password=sudo_password,
        )
        run_command(client, "systemctl daemon-reload", sudo_password=sudo_password)
        run_command(client, f"systemctl enable {SERVICE_NAME}", sudo_password=sudo_password)
        print("✅ Service configuré")

        print("Démarrage du dashboard...")
        run_command(client, f"systemctl restart {SERVICE_NAME}", sudo_password=sudo_password)
        print("✅ Dashboard démarré")

        print(f"✅ Dashboard accessible sur http://{host}:8080")
    finally:
        client.close()

    print("=== Déploiement terminé avec succès ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
