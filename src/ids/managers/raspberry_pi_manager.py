"""
Gestionnaire complet pour Raspberry Pi.

Utilise paramiko pour SSH et gpiozero pour GPIO (si disponible).
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import paramiko

    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False
    logger.warning("paramiko not available. Install with: pip install paramiko")

try:
    from gpiozero import CPUTemperature, DiskUsage, LoadAverage

    GPIOZERO_AVAILABLE = True
except ImportError:
    GPIOZERO_AVAILABLE = False
    # gpiozero est optionnel (seulement sur le Pi)


@dataclass
class RaspberryPiInfo:
    """Informations système du Raspberry Pi."""

    hostname: str
    model: str
    os_version: str
    kernel_version: str
    architecture: str
    cpu_count: int
    total_memory_mb: int
    cpu_temperature: Optional[float] = None
    load_average: Optional[List[float]] = None
    disk_usage_percent: Optional[float] = None


@dataclass
class ServiceStatus:
    """Statut d'un service systemd."""

    name: str
    active: bool
    enabled: bool
    running: bool
    description: str


@dataclass
class DockerContainerStatus:
    """Statut d'un conteneur Docker."""

    container_id: str
    name: str
    image: str
    status: str  # running, exited, etc.
    created: str
    ports: List[str]


class RaspberryPiManager:
    """
    Gestionnaire complet pour Raspberry Pi.

    Fonctionnalités:
    - Connexion SSH
    - Exécution de commandes à distance
    - Monitoring système (CPU, RAM, température)
    - Gestion des services systemd
    - Gestion Docker
    - Transfert de fichiers (SCP)
    - GPIO (si gpiozero disponible)
    """

    def __init__(
        self,
        host: str,
        user: str = "pi",
        port: int = 22,
        ssh_key_path: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """
        Initialise le gestionnaire Raspberry Pi.

        Args:
            host: Adresse IP ou hostname
            user: Utilisateur SSH
            port: Port SSH
            ssh_key_path: Chemin vers la clé SSH privée
            password: Mot de passe SSH (si pas de clé)
        """
        if not PARAMIKO_AVAILABLE:
            raise ImportError("paramiko required. Install with: pip install paramiko")

        self.host = host
        self.user = user
        self.port = port
        self.ssh_key_path = ssh_key_path
        self.password = password
        self._ssh_client: Optional[paramiko.SSHClient] = None

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()

    # =========================================================================
    # SSH Connection Management
    # =========================================================================

    def connect(self) -> None:
        """Établit la connexion SSH."""
        if not PARAMIKO_AVAILABLE:
            raise ImportError("paramiko required")

        self._ssh_client = paramiko.SSHClient()
        self._ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs = {
            "hostname": self.host,
            "port": self.port,
            "username": self.user,
            "timeout": 10,
        }

        if self.ssh_key_path:
            connect_kwargs["key_filename"] = self.ssh_key_path
        elif self.password:
            connect_kwargs["password"] = self.password
        else:
            raise ValueError("Either ssh_key_path or password must be provided")

        try:
            self._ssh_client.connect(**connect_kwargs)
            logger.info(f"SSH connected to {self.user}@{self.host}")
        except Exception as e:
            logger.error(f"SSH connection failed: {e}")
            raise

    def disconnect(self) -> None:
        """Ferme la connexion SSH."""
        if self._ssh_client:
            self._ssh_client.close()
            self._ssh_client = None
            logger.info("SSH disconnected")

    def is_connected(self) -> bool:
        """Vérifie si la connexion SSH est active."""
        if not self._ssh_client:
            return False

        transport = self._ssh_client.get_transport()
        return transport is not None and transport.is_active()

    # =========================================================================
    # Command Execution
    # =========================================================================

    def run_command(
        self,
        command: str,
        sudo: bool = False,
        timeout: int = 30,
    ) -> tuple[int, str, str]:
        """
        Exécute une commande sur le Pi.

        Args:
            command: Commande à exécuter
            sudo: Utiliser sudo
            timeout: Timeout en secondes

        Returns:
            Tuple (exit_code, stdout, stderr)
        """
        if not self._ssh_client:
            raise RuntimeError("Not connected. Call connect() first.")

        if sudo:
            command = f"sudo {command}"

        logger.debug(f"Executing: {command}")

        try:
            stdin, stdout, stderr = self._ssh_client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            stdout_text = stdout.read().decode("utf-8")
            stderr_text = stderr.read().decode("utf-8")

            if exit_code != 0:
                logger.warning(f"Command failed (exit {exit_code}): {command}")
                logger.warning(f"stderr: {stderr_text}")

            return exit_code, stdout_text, stderr_text

        except Exception as e:
            logger.error(f"Command execution error: {e}")
            raise

    # =========================================================================
    # System Information
    # =========================================================================

    def get_system_info(self) -> RaspberryPiInfo:
        """
        Récupère les informations système du Pi.

        Returns:
            Informations système
        """
        # Hostname
        _, hostname, _ = self.run_command("hostname")
        hostname = hostname.strip()

        # Model
        _, model, _ = self.run_command("cat /proc/device-tree/model 2>/dev/null || echo 'Unknown'")
        model = model.strip().replace("\x00", "")

        # OS version
        _, os_version, _ = self.run_command(
            "cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2 | tr -d '\"'"
        )
        os_version = os_version.strip()

        # Kernel
        _, kernel, _ = self.run_command("uname -r")
        kernel = kernel.strip()

        # Architecture
        _, arch, _ = self.run_command("uname -m")
        arch = arch.strip()

        # CPU count
        _, cpu_count, _ = self.run_command("nproc")
        cpu_count_int = int(cpu_count.strip())

        # Total memory
        _, mem_info, _ = self.run_command("grep MemTotal /proc/meminfo | awk '{print $2}'")
        total_memory_mb = int(mem_info.strip()) // 1024

        # CPU temperature
        cpu_temp = None
        _, temp_output, _ = self.run_command(
            "cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo ''"
        )
        if temp_output.strip():
            try:
                cpu_temp = float(temp_output.strip()) / 1000.0
            except ValueError:
                pass

        # Load average
        load_avg = None
        _, load_output, _ = self.run_command("cat /proc/loadavg")
        if load_output.strip():
            parts = load_output.strip().split()
            if len(parts) >= 3:
                load_avg = [float(parts[0]), float(parts[1]), float(parts[2])]

        # Disk usage
        disk_usage = None
        _, disk_output, _ = self.run_command("df / | tail -1 | awk '{print $5}' | sed 's/%//'")
        if disk_output.strip():
            try:
                disk_usage = float(disk_output.strip())
            except ValueError:
                pass

        return RaspberryPiInfo(
            hostname=hostname,
            model=model,
            os_version=os_version,
            kernel_version=kernel,
            architecture=arch,
            cpu_count=cpu_count_int,
            total_memory_mb=total_memory_mb,
            cpu_temperature=cpu_temp,
            load_average=load_avg,
            disk_usage_percent=disk_usage,
        )

    # =========================================================================
    # Service Management
    # =========================================================================

    def get_service_status(self, service_name: str) -> ServiceStatus:
        """
        Récupère le statut d'un service systemd.

        Args:
            service_name: Nom du service (ex: ids2-agent.service)

        Returns:
            Statut du service
        """
        # Check if active
        exit_code, _, _ = self.run_command(f"systemctl is-active {service_name}", sudo=True)
        active = exit_code == 0

        # Check if enabled
        exit_code, _, _ = self.run_command(f"systemctl is-enabled {service_name}", sudo=True)
        enabled = exit_code == 0

        # Get status
        _, status_output, _ = self.run_command(f"systemctl status {service_name}", sudo=True)
        running = "running" in status_output.lower()

        # Get description
        description = ""
        for line in status_output.split("\n"):
            if "Loaded:" in line:
                parts = line.split(";")
                if len(parts) > 1:
                    description = parts[1].strip()
                break

        return ServiceStatus(
            name=service_name,
            active=active,
            enabled=enabled,
            running=running,
            description=description,
        )

    def start_service(self, service_name: str) -> bool:
        """Démarre un service."""
        exit_code, _, _ = self.run_command(f"systemctl start {service_name}", sudo=True)
        return exit_code == 0

    def stop_service(self, service_name: str) -> bool:
        """Arrête un service."""
        exit_code, _, _ = self.run_command(f"systemctl stop {service_name}", sudo=True)
        return exit_code == 0

    def restart_service(self, service_name: str) -> bool:
        """Redémarre un service."""
        exit_code, _, _ = self.run_command(f"systemctl restart {service_name}", sudo=True)
        return exit_code == 0

    def enable_service(self, service_name: str) -> bool:
        """Active un service au démarrage."""
        exit_code, _, _ = self.run_command(f"systemctl enable {service_name}", sudo=True)
        return exit_code == 0

    # =========================================================================
    # Docker Management
    # =========================================================================

    def list_containers(self) -> List[DockerContainerStatus]:
        """
        Liste les conteneurs Docker sur le Pi.

        Returns:
            Liste des conteneurs
        """
        _, output, _ = self.run_command(
            "docker ps -a --format '{{.ID}}|{{.Names}}|{{.Image}}|{{.Status}}|{{.CreatedAt}}|{{.Ports}}'",
            sudo=True,
        )

        containers = []
        for line in output.strip().split("\n"):
            if not line:
                continue

            parts = line.split("|")
            if len(parts) >= 5:
                containers.append(
                    DockerContainerStatus(
                        container_id=parts[0],
                        name=parts[1],
                        image=parts[2],
                        status=parts[3],
                        created=parts[4],
                        ports=parts[5].split(",") if len(parts) > 5 and parts[5] else [],
                    )
                )

        return containers

    def start_container(self, container_name: str) -> bool:
        """Démarre un conteneur Docker."""
        exit_code, _, _ = self.run_command(f"docker start {container_name}", sudo=True)
        return exit_code == 0

    def stop_container(self, container_name: str) -> bool:
        """Arrête un conteneur Docker."""
        exit_code, _, _ = self.run_command(f"docker stop {container_name}", sudo=True)
        return exit_code == 0

    def restart_container(self, container_name: str) -> bool:
        """Redémarre un conteneur Docker."""
        exit_code, _, _ = self.run_command(f"docker restart {container_name}", sudo=True)
        return exit_code == 0

    def docker_compose_up(self, compose_dir: str = "/opt/ids/docker") -> bool:
        """Lance Docker Compose."""
        exit_code, _, _ = self.run_command(
            f"cd {compose_dir} && docker compose up -d", sudo=True, timeout=120
        )
        return exit_code == 0

    def docker_compose_down(self, compose_dir: str = "/opt/ids/docker") -> bool:
        """Arrête Docker Compose."""
        exit_code, _, _ = self.run_command(
            f"cd {compose_dir} && docker compose down", sudo=True, timeout=60
        )
        return exit_code == 0

    # =========================================================================
    # File Transfer
    # =========================================================================

    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """
        Upload un fichier vers le Pi via SFTP.

        Args:
            local_path: Chemin local
            remote_path: Chemin distant

        Returns:
            True si succès
        """
        if not self._ssh_client:
            raise RuntimeError("Not connected")

        try:
            sftp = self._ssh_client.open_sftp()
            sftp.put(local_path, remote_path)
            sftp.close()
            logger.info(f"File uploaded: {local_path} -> {remote_path}")
            return True
        except Exception as e:
            logger.error(f"File upload failed: {e}")
            return False

    def download_file(self, remote_path: str, local_path: str) -> bool:
        """
        Télécharge un fichier depuis le Pi via SFTP.

        Args:
            remote_path: Chemin distant
            local_path: Chemin local

        Returns:
            True si succès
        """
        if not self._ssh_client:
            raise RuntimeError("Not connected")

        try:
            sftp = self._ssh_client.open_sftp()
            sftp.get(remote_path, local_path)
            sftp.close()
            logger.info(f"File downloaded: {remote_path} -> {local_path}")
            return True
        except Exception as e:
            logger.error(f"File download failed: {e}")
            return False

    def upload_directory(self, local_dir: str, remote_dir: str) -> bool:
        """
        Upload un répertoire complet via rsync.

        Args:
            local_dir: Répertoire local
            remote_dir: Répertoire distant

        Returns:
            True si succès
        """
        ssh_key_arg = f"-e 'ssh -i {self.ssh_key_path}'" if self.ssh_key_path else ""

        try:
            result = subprocess.run(
                f"rsync -avz --delete {ssh_key_arg} {local_dir}/ {self.user}@{self.host}:{remote_dir}/",
                shell=True,
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info(f"Directory synced: {local_dir} -> {remote_dir}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Directory sync failed: {e}")
            return False

    # =========================================================================
    # Monitoring
    # =========================================================================

    def get_cpu_usage(self) -> float:
        """
        Récupère l'utilisation CPU.

        Returns:
            Pourcentage d'utilisation CPU
        """
        _, output, _ = self.run_command(
            "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1"
        )
        try:
            return float(output.strip())
        except ValueError:
            return 0.0

    def get_memory_usage(self) -> Dict[str, float]:
        """
        Récupère l'utilisation mémoire.

        Returns:
            Dict avec total, used, free, available en MB
        """
        _, output, _ = self.run_command("free -m | grep Mem:")
        parts = output.strip().split()

        if len(parts) >= 7:
            return {
                "total_mb": float(parts[1]),
                "used_mb": float(parts[2]),
                "free_mb": float(parts[3]),
                "available_mb": float(parts[6]),
                "usage_percent": (float(parts[2]) / float(parts[1])) * 100,
            }

        return {"total_mb": 0, "used_mb": 0, "free_mb": 0, "available_mb": 0, "usage_percent": 0}

    def get_disk_usage(self, path: str = "/") -> Dict[str, Any]:
        """
        Récupère l'utilisation disque.

        Args:
            path: Point de montage

        Returns:
            Dict avec statistiques disque
        """
        _, output, _ = self.run_command(f"df -h {path} | tail -1")
        parts = output.strip().split()

        if len(parts) >= 5:
            return {
                "filesystem": parts[0],
                "size": parts[1],
                "used": parts[2],
                "available": parts[3],
                "usage_percent": float(parts[4].rstrip("%")),
                "mount_point": parts[5] if len(parts) > 5 else path,
            }

        return {}

    def get_temperature(self) -> Optional[float]:
        """
        Récupère la température CPU.

        Returns:
            Température en °C ou None
        """
        _, output, _ = self.run_command(
            "cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo ''"
        )
        if output.strip():
            try:
                return float(output.strip()) / 1000.0
            except ValueError:
                pass
        return None

    # =========================================================================
    # Network Information
    # =========================================================================

    def get_network_interfaces(self) -> Dict[str, Dict[str, Any]]:
        """
        Liste les interfaces réseau et leurs configurations.

        Returns:
            Dict des interfaces avec leurs infos
        """
        _, output, _ = self.run_command("ip -j addr show")

        try:
            import json

            interfaces_data = json.loads(output)

            interfaces = {}
            for iface in interfaces_data:
                name = iface.get("ifname", "")
                addresses = []
                for addr_info in iface.get("addr_info", []):
                    addresses.append(
                        {
                            "family": addr_info.get("family", ""),
                            "local": addr_info.get("local", ""),
                            "prefixlen": addr_info.get("prefixlen", 0),
                        }
                    )

                interfaces[name] = {
                    "state": iface.get("operstate", "unknown"),
                    "mtu": iface.get("mtu", 0),
                    "addresses": addresses,
                }

            return interfaces

        except Exception as e:
            logger.error(f"Failed to parse network interfaces: {e}")
            return {}

    # =========================================================================
    # Deployment Helpers
    # =========================================================================

    def ensure_directory(self, path: str, sudo: bool = False) -> bool:
        """Crée un répertoire s'il n'existe pas."""
        exit_code, _, _ = self.run_command(f"mkdir -p {path}", sudo=sudo)
        return exit_code == 0

    def set_permissions(self, path: str, mode: str = "755", sudo: bool = False) -> bool:
        """Change les permissions d'un fichier/répertoire."""
        exit_code, _, _ = self.run_command(f"chmod -R {mode} {path}", sudo=sudo)
        return exit_code == 0

    def set_owner(self, path: str, owner: str, sudo: bool = True) -> bool:
        """Change le propriétaire d'un fichier/répertoire."""
        exit_code, _, _ = self.run_command(f"chown -R {owner} {path}", sudo=sudo)
        return exit_code == 0


__all__ = [
    "RaspberryPiManager",
    "RaspberryPiInfo",
    "ServiceStatus",
    "DockerContainerStatus",
]
