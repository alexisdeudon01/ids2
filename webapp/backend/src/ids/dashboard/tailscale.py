"""
Tailscale network monitoring.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from ids.datastructures import TailscaleNode

logger = logging.getLogger(__name__)

TAILSCALE_AVAILABLE = False
TAILSCALE_SDK = None
PythonTailscale: type | None = None
try:
    from python_tailscale import Tailscale as PythonTailscale  # type: ignore[assignment,no-redef]

    TAILSCALE_AVAILABLE = True
    TAILSCALE_SDK = "python-tailscale"
except ImportError:
    try:
        from tailscale import Tailscale

        TAILSCALE_AVAILABLE = True
        TAILSCALE_SDK = "tailscale"
    except ImportError:
        logger.warning("tailscale SDK not available. Install with: pip install tailscale")


class TailscaleMonitor:
    """Monitor Tailscale tailnet nodes."""

    def __init__(self, tailnet: str, api_key: str) -> None:
        """
        Initialize Tailscale monitor.

        Args:
            tailnet: Tailnet name
            api_key: Tailscale API key
        """
        self.tailnet = tailnet
        self.api_key = api_key
        self._client: Any = None

        if TAILSCALE_AVAILABLE and TAILSCALE_SDK == "python-tailscale":
            try:
                self._client = PythonTailscale(api_key=api_key, tailnet=tailnet)
                logger.info(f"Python-Tailscale monitor initialized for tailnet: {tailnet}")
            except Exception as e:
                logger.error(f"Failed to initialize python-tailscale client: {e}")
        elif TAILSCALE_AVAILABLE:
            try:
                self._client = Tailscale(tailnet=tailnet, api_key=api_key)
                logger.info(f"Tailscale monitor initialized for tailnet: {tailnet}")
            except Exception as e:
                logger.error(f"Failed to initialize Tailscale client: {e}")
        else:
            logger.warning("Tailscale SDK not available")

    async def get_nodes(self) -> list[TailscaleNode]:
        """
        Get list of authorized nodes in the tailnet.

        Returns:
            List of TailscaleNode objects
        """
        if not self._client:
            return []

        try:
            devices = await self._client.devices()
            nodes: list[TailscaleNode] = []

            device_entries = devices.devices.values() if hasattr(devices, "devices") else devices
            for device in device_entries:
                if not device.authorized:
                    continue

                # Get last seen time
                last_seen: datetime | None = None
                if hasattr(device, "last_seen") and device.last_seen:
                    last_seen = datetime.fromisoformat(str(device.last_seen).replace("Z", "+00:00"))

                # Get primary IP
                ip = ""
                if device.addresses:
                    ip = device.addresses[0]

                node = TailscaleNode(
                    name=device.name or "unknown",
                    ip=ip,
                    online=device.online if hasattr(device, "online") else False,
                    last_seen=last_seen,
                    tags=list(device.tags) if hasattr(device, "tags") else [],
                )
                nodes.append(node)

            return nodes

        except Exception as e:
            logger.error(f"Error getting Tailscale nodes: {e}")
            return []
