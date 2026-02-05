"""
Gestionnaire complet pour Tailscale : nodes, ACLs, connexions.

Utilise la bibliothèque officielle 'tailscale' pour l'API.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

try:
    from tailscale import Tailscale

    TAILSCALE_AVAILABLE = True
except ImportError:
    TAILSCALE_AVAILABLE = False
    logger.warning("tailscale library not available. Install with: pip install tailscale")


@dataclass
class TailscaleDevice:
    """Représente un device dans le tailnet."""

    device_id: str
    name: str
    hostname: str
    addresses: list[str]
    os: str
    online: bool
    authorized: bool
    tags: list[str] = field(default_factory=list)
    last_seen: str | None = None
    user: str | None = None


@dataclass
class TailscaleKey:
    """Représente une clé d'authentification Tailscale."""

    key_id: str
    key: str
    description: str
    created: str
    expires: str | None = None
    revoked: bool = False
    reusable: bool = False
    ephemeral: bool = False
    preauthorized: bool = False
    tags: list[str] = field(default_factory=list)


class TailscaleManager:
    """
    Gestionnaire complet pour Tailscale.

    Fonctionnalités:
    - Liste/ajout/suppression de devices
    - Gestion des auth keys
    - Gestion des ACLs et tags
    - Tests de connectivité (ping)
    - Monitoring du réseau
    """

    def __init__(self, api_key: str, tailnet: str):
        """
        Initialise le gestionnaire Tailscale.

        Args:
            api_key: Clé API Tailscale (tskey-api-...)
            tailnet: Nom du tailnet (ex: example.com ou username)
        """
        if not TAILSCALE_AVAILABLE:
            raise ImportError("tailscale library required. Install with: pip install tailscale")

        self.api_key = api_key
        self.tailnet = tailnet
        self._client: Tailscale | None = None

    async def __aenter__(self):
        """Context manager async entry."""
        self._client = Tailscale(tailnet=self.tailnet, api_key=self.api_key)
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager async exit."""
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)

    # =========================================================================
    # Device Management
    # =========================================================================

    async def list_devices(self) -> list[TailscaleDevice]:
        """
        Liste tous les devices du tailnet.

        Returns:
            Liste des devices
        """
        if not self._client:
            raise RuntimeError("Manager not initialized. Use async with context.")

        devices_response = await self._client.devices()
        devices = []

        for device_id, device in devices_response.devices.items():
            devices.append(
                TailscaleDevice(
                    device_id=device_id,
                    name=device.name or "unknown",
                    hostname=device.hostname or "unknown",
                    addresses=device.addresses or [],
                    os=device.os or "unknown",
                    online=device.online or False,
                    authorized=device.authorized or False,
                    tags=device.tags or [],
                    last_seen=device.last_seen,
                    user=device.user,
                )
            )

        return devices

    async def get_device(self, device_id: str) -> TailscaleDevice | None:
        """
        Récupère un device spécifique par son ID.

        Args:
            device_id: ID du device

        Returns:
            Device ou None si non trouvé
        """
        devices = await self.list_devices()
        for device in devices:
            if device.device_id == device_id:
                return device
        return None

    async def find_device_by_ip(self, ip_address: str) -> TailscaleDevice | None:
        """
        Trouve un device par son adresse IP Tailscale.

        Args:
            ip_address: Adresse IP (ex: 100.118.244.54)

        Returns:
            Device ou None si non trouvé
        """
        devices = await self.list_devices()
        for device in devices:
            if ip_address in device.addresses:
                return device
        return None

    async def delete_device(self, device_id: str) -> bool:
        """
        Supprime un device du tailnet.

        Args:
            device_id: ID du device à supprimer

        Returns:
            True si succès
        """
        if not self._client:
            raise RuntimeError("Manager not initialized. Use async with context.")

        try:
            await self._client.delete_device(device_id)
            logger.info(f"Device deleted: {device_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete device {device_id}: {e}")
            return False

    async def authorize_device(self, device_id: str) -> bool:
        """
        Autorise un device dans le tailnet.

        Args:
            device_id: ID du device

        Returns:
            True si succès
        """
        if not self._client:
            raise RuntimeError("Manager not initialized. Use async with context.")

        try:
            await self._client.set_device_authorized(device_id, authorized=True)
            logger.info(f"Device authorized: {device_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to authorize device {device_id}: {e}")
            return False

    async def set_device_tags(self, device_id: str, tags: list[str]) -> bool:
        """
        Définit les tags d'un device.

        Args:
            device_id: ID du device
            tags: Liste des tags (ex: ["tag:server", "tag:production"])

        Returns:
            True si succès
        """
        if not self._client:
            raise RuntimeError("Manager not initialized. Use async with context.")

        try:
            await self._client.set_device_tags(device_id, tags=tags)
            logger.info(f"Device tags updated: {device_id} -> {tags}")
            return True
        except Exception as e:
            logger.error(f"Failed to set tags for device {device_id}: {e}")
            return False

    # =========================================================================
    # Auth Keys Management
    # =========================================================================

    async def list_keys(self) -> list[TailscaleKey]:
        """
        Liste toutes les auth keys du tailnet.

        Returns:
            Liste des clés
        """
        if not self._client:
            raise RuntimeError("Manager not initialized. Use async with context.")

        keys_response = await self._client.keys()
        keys = []

        for key_data in keys_response.keys:
            keys.append(
                TailscaleKey(
                    key_id=key_data.id,
                    key=key_data.key,
                    description=key_data.description or "",
                    created=key_data.created,
                    expires=key_data.expires,
                    revoked=key_data.revoked or False,
                    reusable=key_data.capabilities.get("devices", {})
                    .get("create", {})
                    .get("reusable", False),
                    ephemeral=key_data.capabilities.get("devices", {})
                    .get("create", {})
                    .get("ephemeral", False),
                    preauthorized=key_data.capabilities.get("devices", {})
                    .get("create", {})
                    .get("preauthorized", False),
                    tags=key_data.capabilities.get("devices", {}).get("create", {}).get("tags", []),
                )
            )

        return keys

    async def create_auth_key(
        self,
        description: str = "Generated by IDS",
        reusable: bool = True,
        ephemeral: bool = False,
        preauthorized: bool = True,
        tags: list[str] | None = None,
        expiry_seconds: int | None = None,
    ) -> str:
        """
        Crée une nouvelle auth key.

        Args:
            description: Description de la clé
            reusable: Clé réutilisable
            ephemeral: Clé éphémère (device supprimé à la déconnexion)
            preauthorized: Device autorisé automatiquement
            tags: Tags à appliquer au device
            expiry_seconds: Durée de validité en secondes

        Returns:
            La clé générée (tskey-auth-...)
        """
        if not self._client:
            raise RuntimeError("Manager not initialized. Use async with context.")

        capabilities = {
            "devices": {
                "create": {
                    "reusable": reusable,
                    "ephemeral": ephemeral,
                    "preauthorized": preauthorized,
                }
            }
        }

        if tags:
            capabilities["devices"]["create"]["tags"] = tags

        key_response = await self._client.create_key(
            capabilities=capabilities,
            expiry_seconds=expiry_seconds or 90 * 24 * 3600,  # 90 jours par défaut
            description=description,
        )

        logger.info(f"Auth key created: {key_response.key[:20]}...")
        return key_response.key

    async def delete_key(self, key_id: str) -> bool:
        """
        Supprime une auth key.

        Args:
            key_id: ID de la clé

        Returns:
            True si succès
        """
        if not self._client:
            raise RuntimeError("Manager not initialized. Use async with context.")

        try:
            await self._client.delete_key(key_id)
            logger.info(f"Auth key deleted: {key_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete key {key_id}: {e}")
            return False

    # =========================================================================
    # Connectivity Testing
    # =========================================================================

    def ping_device(self, ip_address: str, count: int = 4, timeout: int = 10) -> float | None:
        """
        Ping un device via Tailscale CLI.

        Args:
            ip_address: Adresse IP Tailscale
            count: Nombre de pings
            timeout: Timeout en secondes

        Returns:
            Latence moyenne en ms, ou None si échec
        """
        try:
            result = subprocess.run(
                ["tailscale", "ping", "-c", str(count), ip_address],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )

            if result.returncode != 0:
                logger.warning(f"Ping failed to {ip_address}")
                return None

            # Parse latency from output
            import re

            matches = re.findall(r"in\s+(\d+(?:\.\d+)?)\s*ms", result.stdout)
            if matches:
                latencies = [float(m) for m in matches]
                return sum(latencies) / len(latencies)

            return None

        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError) as e:
            logger.error(f"Ping error to {ip_address}: {e}")
            return None

    async def check_device_connectivity(self, device_id: str) -> bool:
        """
        Vérifie si un device est accessible.

        Args:
            device_id: ID du device

        Returns:
            True si accessible
        """
        device = await self.get_device(device_id)
        if not device or not device.online:
            return False

        if not device.addresses:
            return False

        # Ping la première adresse
        latency = self.ping_device(device.addresses[0], count=1, timeout=5)
        return latency is not None

    # =========================================================================
    # Network Status
    # =========================================================================

    async def get_network_status(self) -> dict[str, Any]:
        """
        Récupère le statut complet du réseau.

        Returns:
            Dictionnaire avec statistiques du réseau
        """
        devices = await self.list_devices()

        online_devices = [d for d in devices if d.online]
        authorized_devices = [d for d in devices if d.authorized]

        # Compter par OS
        os_count: dict[str, int] = {}
        for device in devices:
            os_count[device.os] = os_count.get(device.os, 0) + 1

        # Compter par tags
        tag_count: dict[str, int] = {}
        for device in devices:
            for tag in device.tags:
                tag_count[tag] = tag_count.get(tag, 0) + 1

        return {
            "timestamp": datetime.now().isoformat(),
            "tailnet": self.tailnet,
            "total_devices": len(devices),
            "online_devices": len(online_devices),
            "authorized_devices": len(authorized_devices),
            "offline_devices": len(devices) - len(online_devices),
            "os_distribution": os_count,
            "tag_distribution": tag_count,
            "devices": [
                {
                    "id": d.device_id,
                    "name": d.name,
                    "hostname": d.hostname,
                    "addresses": d.addresses,
                    "os": d.os,
                    "online": d.online,
                    "authorized": d.authorized,
                    "tags": d.tags,
                }
                for d in devices
            ],
        }


# =========================================================================
# Helper Functions
# =========================================================================


async def connect_to_tailnet(api_key: str, tailnet: str) -> TailscaleManager:
    """
    Crée et initialise une connexion au tailnet.

    Args:
        api_key: Clé API Tailscale
        tailnet: Nom du tailnet

    Returns:
        TailscaleManager initialisé

    Example:
        async with connect_to_tailnet(api_key, tailnet) as manager:
            devices = await manager.list_devices()
    """
    manager = TailscaleManager(api_key, tailnet)
    return manager


async def ensure_device_online(
    manager: TailscaleManager,
    device_identifier: str,
    timeout: int = 60,
) -> bool:
    """
    Attend qu'un device soit en ligne.

    Args:
        manager: TailscaleManager
        device_identifier: ID ou IP du device
        timeout: Timeout en secondes

    Returns:
        True si le device est en ligne
    """
    start_time = datetime.now()

    while (datetime.now() - start_time).total_seconds() < timeout:
        # Chercher par ID
        device = await manager.get_device(device_identifier)

        # Si pas trouvé par ID, chercher par IP
        if not device:
            device = await manager.find_device_by_ip(device_identifier)

        if device and device.online:
            logger.info(f"Device {device.name} is online")
            return True

        await asyncio.sleep(5)

    logger.warning(f"Device {device_identifier} did not come online within {timeout}s")
    return False


__all__ = [
    "TailscaleDevice",
    "TailscaleKey",
    "TailscaleManager",
    "connect_to_tailnet",
    "ensure_device_online",
]
