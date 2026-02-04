"""
Deploy helper - automatisation du build et du push vers le Raspberry Pi.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Sequence

import requests

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeployConfig:
    pi_host: str
    pi_user: str = "pi"
    project_dir: str = "/opt/ids2"
    image_name: str = "ids2-agent"
    image_tag: str = "latest"
    dockerfile: str = "Dockerfile"
    compose_path: str = "docker/docker-compose.yml"
    requirements_path: str = "requirements.txt"
    config_path: str = "config.yaml"
    secret_path: str = "secret.json"
    opensearch_endpoint: Optional[str] = None
    ssh_options: Sequence[str] = field(
        default_factory=lambda: ("-o", "BatchMode=yes", "-o", "ConnectTimeout=5")
    )


class CommandRunner:
    """Abstraction d'execution de commandes."""

    def run(self, command: Sequence[str], check: bool = True) -> subprocess.CompletedProcess:
        logger.debug("Commande: %s", " ".join(command))
        return subprocess.run(command, check=check)


class DeployHelper:
    """Automatise le build/push et l'installation sur le Raspberry Pi."""

    def __init__(self, config: DeployConfig, runner: Optional[CommandRunner] = None) -> None:
        self.config = config
        self.runner = runner or CommandRunner()

    def deploy(self) -> None:
        """Pipeline complet de deploiement."""
        self.verifier_connectivite()
        self.build_image()
        tar_path = self.save_image()
        self.transfer_image(tar_path)
        self.sync_files()
        self.enable_services()

    def verifier_connectivite(self) -> None:
        """Verifie SSH, Docker local et accessibilite OpenSearch."""
        self._run(["docker", "info"])
        self._ssh("echo ok")
        if self.config.opensearch_endpoint:
            self._check_opensearch(self.config.opensearch_endpoint)

    def build_image(self) -> None:
        """Construit l'image Docker."""
        self._run(
            [
                "docker",
                "build",
                "-t",
                self.image_ref,
                "-f",
                self.config.dockerfile,
                ".",
            ]
        )

    def save_image(self) -> Path:
        """Sauvegarde l'image Docker en tar."""
        tar_path = (
            Path(tempfile.gettempdir()) / f"{self.config.image_name}-{self.config.image_tag}.tar"
        )
        self._run(["docker", "save", "-o", str(tar_path), self.image_ref])
        return tar_path

    def transfer_image(self, tar_path: Path) -> None:
        """Transfere l'image sur le Pi et la charge."""
        remote_tar = f"/tmp/{tar_path.name}"
        self._scp(tar_path, remote_tar)
        self._ssh(f"docker load -i {remote_tar}")
        self._ssh(f"rm -f {remote_tar}")

    def sync_files(self) -> None:
        """Sync requirements, config et compose sur le Pi."""
        files = [
            (Path(self.config.requirements_path), "requirements.txt"),
            (Path(self.config.config_path), "config.yaml"),
            (Path(self.config.secret_path), "secret.json"),
            (Path(self.config.compose_path), "docker/docker-compose.yml"),
        ]

        for src, rel_dest in files:
            if not src.exists():
                logger.warning("Fichier absent, ignore: %s", src)
                continue
            dest = Path(self.config.project_dir) / rel_dest
            self._ssh(f"mkdir -p {dest.parent}")
            self._scp(src, str(dest))

    def enable_services(self) -> None:
        """Active systemd et demarre la stack Docker."""
        self._ssh("sudo systemctl daemon-reload")
        self._ssh("sudo systemctl enable suricata.service")
        self._ssh("sudo systemctl enable ids2-agent.service")
        self._ssh("sudo systemctl enable network-eth0-only.service")
        compose = Path(self.config.project_dir) / "docker/docker-compose.yml"
        self._ssh(f"sudo docker compose -f {compose} up -d")

    def _check_opensearch(self, endpoint: str) -> None:
        try:
            response = requests.get(endpoint, timeout=5)
            if response.status_code >= 500:
                raise RuntimeError(f"OpenSearch indisponible: {response.status_code}")
        except requests.RequestException as exc:
            raise RuntimeError(f"OpenSearch indisponible: {exc}") from exc

    @property
    def image_ref(self) -> str:
        return f"{self.config.image_name}:{self.config.image_tag}"

    def _run(self, command: Sequence[str]) -> None:
        self.runner.run(list(command), check=True)

    def _ssh(self, command: str) -> None:
        ssh_cmd = [
            "ssh",
            *self.config.ssh_options,
            f"{self.config.pi_user}@{self.config.pi_host}",
            command,
        ]
        self._run(ssh_cmd)

    def _scp(self, source: Path, dest: str) -> None:
        scp_cmd = [
            "scp",
            *self.config.ssh_options,
            str(source),
            f"{self.config.pi_user}@{self.config.pi_host}:{dest}",
        ]
        self._run(scp_cmd)
