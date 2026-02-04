"""
Network Connectivity Testing Implementation.

Single Responsibility: Only handles ping/connectivity testing.
"""

from __future__ import annotations

import json
import re
import subprocess

from .interfaces import BaseConnectivityTester


class TailscalePingTester(BaseConnectivityTester):
    """
    Connectivity tester using `tailscale ping` CLI command.

    Single Responsibility: Only measures latency via tailscale ping.
    Liskov Substitution: Can replace any BaseConnectivityTester.
    """

    def __init__(self, timeout: int = 15):
        """
        Initialize the tester.

        Args:
            timeout: Timeout in seconds for ping operations.
        """
        self.timeout = timeout

    def ping(self, ip: str, count: int = 3) -> float | None:
        """
        Ping a device using tailscale ping and return average latency.

        Args:
            ip: Tailscale IP address to ping
            count: Number of pings to send

        Returns:
            Average latency in milliseconds, or None if unreachable.
        """
        try:
            result = subprocess.run(
                ["tailscale", "ping", "-c", str(count), ip],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,  # We check returncode manually
            )

            if result.returncode != 0:
                return None

            # Parse latency from output like "pong from host (100.x.x.x) via DERP in 45ms"
            latencies = re.findall(r"in\s+([\d.]+)\s*ms", result.stdout, re.IGNORECASE)

            if latencies:
                return sum(float(lat) for lat in latencies) / len(latencies)

        except subprocess.TimeoutExpired:
            return None
        except FileNotFoundError:
            # tailscale CLI not installed
            return None
        except OSError:
            # Other OS-level errors
            return None

        return None

    def is_tailscale_installed(self) -> bool:
        """Check if tailscale CLI is available."""
        try:
            result = subprocess.run(
                ["tailscale", "version"],
                capture_output=True,
                timeout=5,
                check=False,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False

    def is_connected(self) -> bool:
        """Check if currently connected to a tailnet."""
        try:
            result = subprocess.run(
                ["tailscale", "status", "--json"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode != 0:
                return False

            data = json.loads(result.stdout)
            return data.get("BackendState") == "Running"
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError, json.JSONDecodeError):
            return False

    def get_self_ip(self) -> str | None:
        """Get the local Tailscale IP address."""
        try:
            result = subprocess.run(
                ["tailscale", "ip", "-4"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        return None


class MockConnectivityTester(BaseConnectivityTester):
    """
    Mock connectivity tester for testing purposes.

    Liskov Substitution: Behaves like a real tester but returns fake data.
    """

    def __init__(
        self,
        default_latency: float = 50.0,
        failure_ips: list[str] | None = None,
    ):
        """
        Initialize mock tester.

        Args:
            default_latency: Default latency to return for all pings
            failure_ips: List of IPs that should return None (unreachable)
        """
        self.default_latency = default_latency
        self.failure_ips = failure_ips or []

    def ping(self, ip: str, count: int = 3) -> float | None:
        """Return mock latency."""
        del count  # Unused in mock
        if ip in self.failure_ips:
            return None
        return self.default_latency
