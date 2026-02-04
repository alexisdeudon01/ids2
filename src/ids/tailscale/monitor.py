"""
Tailnet Monitor - High-level orchestrator.

Dependency Inversion: Depends on abstractions (protocols), not implementations.
Open/Closed: Behavior can be extended by injecting different implementations.
"""

from __future__ import annotations

import asyncio
import getpass
from typing import Optional

from .api_client import BaseAPIClient, create_api_client
from .connectivity import BaseConnectivityTester, TailscalePingTester
from .interfaces import NetworkVisualizer
from .models import HealthMetrics, NetworkSnapshot


class TailnetMonitor:
    """
    High-level orchestrator for Tailscale network monitoring.

    SOLID Principles Applied:
    - Single Responsibility: Orchestrates, doesn't implement details
    - Open/Closed: Extensible via dependency injection
    - Liskov Substitution: Works with any implementation of protocols
    - Interface Segregation: Uses focused interfaces
    - Dependency Inversion: Depends on abstractions

    Usage:
        monitor = TailnetMonitor(tailnet="example.com", api_key="tskey-api-xxx")
        snapshot = await monitor.capture_state()
        monitor.measure_latencies(snapshot)
        monitor.visualize(snapshot, "network.html")
    """

    def __init__(
        self,
        tailnet: str,
        api_key: str,
        api_client: Optional[BaseAPIClient] = None,
        connectivity_tester: Optional[BaseConnectivityTester] = None,
        visualizer: Optional[NetworkVisualizer] = None,
    ):
        """
        Initialize the monitor with optional dependency injection.

        Args:
            tailnet: Tailnet name (e.g., "example.com")
            api_key: Tailscale API key
            api_client: Optional custom API client (default: auto-detect best)
            connectivity_tester: Optional custom tester (default: TailscalePingTester)
            visualizer: Optional custom visualizer (default: PyvisVisualizer)
        """
        self.tailnet = tailnet
        self._api_key = api_key  # Never exposed

        # Dependency Injection with sensible defaults
        self._api_client = api_client or create_api_client(tailnet, api_key)
        self._connectivity_tester = connectivity_tester or TailscalePingTester()
        self._visualizer = visualizer

    async def capture_state(self, measure_latency: bool = False) -> NetworkSnapshot:
        """
        Capture current network state from the Tailscale API.

        Args:
            measure_latency: If True, also measure latency to all online nodes

        Returns:
            NetworkSnapshot with all devices
        """
        devices = await self._api_client.get_devices()
        snapshot = NetworkSnapshot.create(self.tailnet, devices)

        if measure_latency:
            self.measure_latencies(snapshot)

        return snapshot

    def measure_latencies(self, snapshot: NetworkSnapshot) -> None:
        """
        Measure latency to all online devices in the snapshot.

        Updates device.latency_ms in place.

        Args:
            snapshot: NetworkSnapshot to update
        """
        online_devices = snapshot.get_online_devices()

        for device in online_devices:
            if device.tailscale_ip:
                device.latency_ms = self._connectivity_tester.ping(device.tailscale_ip)

    def get_health_metrics(self, snapshot: NetworkSnapshot) -> HealthMetrics:
        """
        Calculate health metrics from a snapshot.

        Args:
            snapshot: NetworkSnapshot to analyze

        Returns:
            HealthMetrics with availability and latency stats
        """
        return HealthMetrics.from_snapshot(snapshot)

    def visualize(
        self,
        snapshot: NetworkSnapshot,
        output_path: str = "network_health_map.html",
    ) -> str:
        """
        Generate an interactive visualization of the network.

        Args:
            snapshot: NetworkSnapshot to visualize
            output_path: Output HTML file path

        Returns:
            Path to generated HTML file
        """
        if self._visualizer is None:
            # Lazy import to avoid pyvis dependency if not needed
            from .visualizer import PyvisVisualizer

            self._visualizer = PyvisVisualizer()

        return self._visualizer.generate(snapshot, output_path)

    async def check_device_connectivity(self, target_ip: str) -> bool:
        """
        Check if a specific device is connected and reachable.

        Useful for CI/CD connectivity verification.

        Args:
            target_ip: Tailscale IP to verify

        Returns:
            True if device is found, authorized, and reachable
        """
        snapshot = await self.capture_state(measure_latency=False)

        device = snapshot.get_device_by_ip(target_ip)
        if not device:
            print(f"❌ Device not found for IP: {target_ip}")
            return False

        if not device.authorized:
            print(f"❌ Device not authorized: {device.hostname}")
            return False

        if not device.is_online:
            print(f"❌ Device offline: {device.hostname}")
            return False

        # Ping test
        latency = self._connectivity_tester.ping(target_ip)
        if latency is None:
            print(f"⚠️ Device found but unreachable: {device.hostname}")
            return False

        print(f"✅ Device OK: {device.hostname} ({target_ip}) - {latency:.1f}ms")
        return True


async def run_monitor_async(
    tailnet: str,
    api_key: str,
    output_file: str = "network_health_map.html",
) -> NetworkSnapshot:
    """
    Async function to run the full monitoring cycle.

    Args:
        tailnet: Tailnet name
        api_key: Tailscale API key
        output_file: Output HTML file for visualization

    Returns:
        NetworkSnapshot with all measurements
    """
    print("=" * 60)
    print("  🌐 TAILSCALE MESH NETWORK MONITOR")
    print("=" * 60)
    print()

    monitor = TailnetMonitor(tailnet=tailnet, api_key=api_key)

    # Capture state
    print("🔍 Capturing Network State...")
    snapshot = await monitor.capture_state(measure_latency=False)
    print(f"   Found {snapshot.total_nodes} nodes ({snapshot.online_nodes} online)")
    print()

    # Measure latencies
    print("📡 Measuring Latencies...")
    monitor.measure_latencies(snapshot)
    if snapshot.average_latency_ms:
        print(f"   Average: {snapshot.average_latency_ms:.1f}ms")
    print()

    # Display health
    health = monitor.get_health_metrics(snapshot)
    print("📊 Network Health:")
    print(f"   Availability: {health.availability_percent:.1f}%")
    print(f"   Reachable: {health.reachable_nodes}/{health.online_nodes} online nodes")
    if health.average_latency_ms:
        print(f"   Latency: {health.min_latency_ms:.1f}ms - {health.max_latency_ms:.1f}ms")
    print()

    # List devices
    print("📋 Devices:")
    for dev in snapshot.devices:
        icon = "🟢" if dev.is_online else "🔴"
        lat = f"{dev.latency_ms:.1f}ms" if dev.is_reachable else "N/A"
        print(f"   {icon} {dev.hostname:<20} {dev.tailscale_ip:<16} {lat}")
    print()

    # Generate visualization
    print("🎨 Generating Visualization...")
    output = monitor.visualize(snapshot, output_file)
    print(f"   Saved to: {output}")
    print()

    print("✅ Done!")
    return snapshot


def run_monitor_interactive() -> None:
    """
    Run the monitor interactively, prompting for credentials.

    Entry point for CLI usage.
    """
    print("=" * 60)
    print("  🌐 TAILSCALE MESH NETWORK MONITOR")
    print("=" * 60)
    print()

    # Secure input
    api_key = getpass.getpass("🔑 Enter Tailscale API Key: ")
    if not api_key:
        print("❌ API key is required.")
        return

    tailnet = input("📡 Enter Tailnet Name: ").strip()
    if not tailnet:
        print("❌ Tailnet name is required.")
        return

    print()
    asyncio.run(run_monitor_async(tailnet, api_key))


# For CLI execution
if __name__ == "__main__":
    run_monitor_interactive()
