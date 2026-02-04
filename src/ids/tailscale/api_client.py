"""
Tailscale API Client Implementation.

Single Responsibility: Only handles API communication.
Uses the official Python `tailscale` library.
"""

from __future__ import annotations

from typing import List

from .interfaces import BaseAPIClient
from .models import DeviceState

# Use the Python tailscale library
try:
    from tailscale import Tailscale

    TAILSCALE_LIB_AVAILABLE = True
except ImportError:
    TAILSCALE_LIB_AVAILABLE = False


class TailscaleLibraryClient(BaseAPIClient):
    """
    API client using the official Python `tailscale` library.

    Single Responsibility: Only fetches devices via the Tailscale API.
    Liskov Substitution: Can replace any BaseAPIClient implementation.
    """

    def __init__(self, tailnet: str, api_key: str):
        """
        Initialize the client.

        Args:
            tailnet: Tailnet name (e.g., "example.com" or "user@github")
            api_key: Tailscale API key (tskey-api-...)
        """
        if not TAILSCALE_LIB_AVAILABLE:
            raise ImportError("The 'tailscale' library is required. " "Install with: pip install tailscale")
        super().__init__(tailnet, api_key)

    async def get_devices(self) -> List[DeviceState]:
        """
        Fetch all devices from the Tailscale API.

        Returns:
            List of DeviceState objects representing all devices.
        """
        async with Tailscale(tailnet=self.tailnet, api_key=self._api_key) as client:
            response = await client.devices()

            devices: List[DeviceState] = []
            for device_id, device in response.devices.items():
                addresses = device.addresses or []
                # Get first IPv4 address
                ipv4 = next(
                    (addr for addr in addresses if "." in addr and not addr.startswith("fd7a:")),
                    addresses[0] if addresses else "",
                )

                devices.append(
                    DeviceState(
                        device_id=device_id,
                        hostname=device.hostname or device.name or "unknown",
                        tailscale_ip=ipv4,
                        os=device.os or "unknown",
                        status="online" if getattr(device, "online", False) else "offline",
                        last_seen=str(device.last_seen) if device.last_seen else "N/A",
                        tags=device.tags or [],
                        authorized=device.authorized if hasattr(device, "authorized") else True,
                        client_version=getattr(device, "client_version", ""),
                    )
                )

            return devices


class RequestsAPIClient(BaseAPIClient):
    """
    Fallback API client using requests library.

    Used when the tailscale library is not available.
    """

    def __init__(self, tailnet: str, api_key: str):
        super().__init__(tailnet, api_key)
        self._base_url = f"https://api.tailscale.com/api/v2/tailnet/{tailnet}"

    async def get_devices(self) -> List[DeviceState]:
        """Fetch devices using requests library."""
        import requests  # type: ignore[import-untyped]

        response = requests.get(
            f"{self._base_url}/devices",
            auth=(self._api_key, ""),
            timeout=30,
        )
        response.raise_for_status()
        data = response.json().get("devices", [])

        devices: List[DeviceState] = []
        for d in data:
            addresses = d.get("addresses", [])
            devices.append(
                DeviceState(
                    device_id=d.get("id", ""),
                    hostname=d.get("hostname", "unknown"),
                    tailscale_ip=addresses[0] if addresses else "",
                    os=d.get("os", "unknown"),
                    status="online" if d.get("online", False) else "offline",
                    last_seen=d.get("lastSeen", "N/A"),
                    tags=d.get("tags", []),
                    authorized=d.get("authorized", True),
                    client_version=d.get("clientVersion", ""),
                )
            )

        return devices


def create_api_client(tailnet: str, api_key: str) -> BaseAPIClient:
    """
    Factory function to create the best available API client.

    Returns TailscaleLibraryClient if available, otherwise RequestsAPIClient.
    """
    if TAILSCALE_LIB_AVAILABLE:
        return TailscaleLibraryClient(tailnet, api_key)
    return RequestsAPIClient(tailnet, api_key)
