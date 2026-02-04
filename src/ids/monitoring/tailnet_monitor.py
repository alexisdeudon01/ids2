"""Tailscale mesh network monitoring and visualization."""

import getpass
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

import requests
from pyvis.network import Network  # type: ignore[import-not-found]


@dataclass
class DeviceState:
    """Represents the state of a single Tailscale device."""

    hostname: str
    tailscale_ip: str
    os: str
    status: str  # "online" or "offline"
    last_seen: str
    device_id: str
    tags: List[str] = field(default_factory=list)
    latency: Optional[float] = None  # Populated by connectivity check


@dataclass
class NetworkSnapshot:
    """Point-in-time view of the entire Tailscale mesh network."""

    timestamp: str
    total_nodes: int
    online_nodes: int
    devices: List[DeviceState] = field(default_factory=list)
    average_latency: Optional[float] = None


class TailnetMonitor:
    """Monitor and visualize Tailscale mesh network health."""

    def __init__(self, api_key: str, tailnet_name: str):
        """
        Initialize the Tailnet monitor.

        Args:
            api_key: Tailscale API key (tskey-...)
            tailnet_name: Tailnet name (e.g., 'example.com' or 'user@github')
        """
        self.auth = (api_key, "")
        self.tailnet = tailnet_name
        self.base_url = f"https://api.tailscale.com/api/v2/tailnet/{tailnet_name}"

    def get_current_state(self) -> NetworkSnapshot:
        """
        Fetch the current network state from Tailscale API.

        Returns:
            NetworkSnapshot with all devices and their states
        """
        res = requests.get(f"{self.base_url}/devices", auth=self.auth, timeout=10)
        res.raise_for_status()
        data = res.json().get("devices", [])

        devices = []
        for d in data:
            devices.append(
                DeviceState(
                    hostname=d["hostname"],
                    tailscale_ip=d["addresses"][0] if d.get("addresses") else "N/A",
                    os=d.get("os", "unknown"),
                    status="online" if d.get("online") else "offline",
                    last_seen=d.get("lastSeen", "N/A"),
                    device_id=d.get("id", ""),
                    tags=d.get("tags", []),
                )
            )

        return NetworkSnapshot(
            timestamp=datetime.now().isoformat(),
            total_nodes=len(devices),
            online_nodes=sum(1 for d in devices if d.status == "online"),
            devices=devices,
        )

    def check_connectivity(self, target_ip: str, count: int = 1) -> float:
        """
        Measure real-time latency to a specific node using tailscale ping.

        Args:
            target_ip: Tailscale IP to ping
            count: Number of ping packets (default: 1)

        Returns:
            Average latency in ms, or -1.0 if unreachable
        """
        try:
            output = subprocess.check_output(
                ["tailscale", "ping", "-c", str(count), target_ip],
                timeout=5,
                stderr=subprocess.DEVNULL,
            ).decode()

            # Parse latency from output (format: "pong from ... via ... in 12.34ms")
            if "ms" in output:
                for line in output.splitlines():
                    if "pong from" in line and "ms" in line:
                        latency_str = line.split("in")[-1].strip().replace("ms", "")
                        return float(latency_str)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError):
            return -1.0
        return -1.0

    def measure_mesh_latency(self, snapshot: NetworkSnapshot) -> NetworkSnapshot:
        """
        Measure latency to all online nodes and calculate average.

        Args:
            snapshot: Network snapshot to enrich with latency data

        Returns:
            Updated snapshot with latency measurements
        """
        latencies = []
        for device in snapshot.devices:
            if device.status == "online" and device.tailscale_ip != "N/A":
                print(f"Pinging {device.hostname} ({device.tailscale_ip})...")
                device.latency = self.check_connectivity(device.tailscale_ip)
                if device.latency > 0:
                    latencies.append(device.latency)

        if latencies:
            snapshot.average_latency = sum(latencies) / len(latencies)

        return snapshot

    def generate_interactive_graph(
        self, snapshot: NetworkSnapshot, output_file: str = "network_health_map.html"
    ):
        """
        Generate an interactive network graph using Pyvis.

        Args:
            snapshot: Network snapshot to visualize
            output_file: Output HTML file path
        """
        net = Network(
            height="700px",
            width="100%",
            bgcolor="#1a1a1a",
            font_color="white",
            notebook=False,
        )
        net.toggle_physics(True)

        # Central core node
        net.add_node(
            "CORE",
            label=f"TAILNET\n{self.tailnet}",
            shape="diamond",
            color="#3498db",
            size=40,
            title=f"Total: {snapshot.total_nodes} | Online: {snapshot.online_nodes}",
        )

        for dev in snapshot.devices:
            # Color based on status
            color = "#2ecc71" if dev.status == "online" else "#e74c3c"

            # Size based on latency (lower latency = larger node)
            if dev.latency and dev.latency > 0:
                # Inverse scale: 50ms -> size 30, 200ms -> size 10
                size = max(10, 50 - (dev.latency / 5))
            else:
                size = 15

            # Tooltip with device info
            title = (
                f"<b>{dev.hostname}</b><br>"
                f"OS: {dev.os}<br>"
                f"IP: {dev.tailscale_ip}<br>"
                f"Status: {dev.status}<br>"
                f"Last Seen: {dev.last_seen}<br>"
                f"Latency: {dev.latency if dev.latency and dev.latency > 0 else 'N/A'} ms<br>"
                f"Tags: {', '.join(dev.tags) if dev.tags else 'None'}<br>"
                f"<a href='https://login.tailscale.com/admin/machines/{dev.device_id}' target='_blank'>View in Console</a>"
            )

            net.add_node(
                dev.hostname,
                label=dev.hostname,
                title=title,
                color=color,
                shape="dot",
                size=size,
            )
            net.add_edge("CORE", dev.hostname, weight=1)

        # Add timestamp and stats
        net.add_node(
            "STATS",
            label=f"Snapshot: {snapshot.timestamp[:19]}\nAvg Latency: {snapshot.average_latency:.2f}ms"
            if snapshot.average_latency
            else f"Snapshot: {snapshot.timestamp[:19]}",
            shape="box",
            color="#95a5a6",
            size=20,
        )

        net.show(output_file)
        print(f"🌍 Interactive Network Health Map generated at '{output_file}'")


def run_interactive_monitor():
    """Run the Tailnet monitor in interactive mode."""
    # Secure inputs
    api_key = getpass.getpass("Enter Tailscale API Key: ")
    tailnet = input("Enter Tailnet Name: ")

    monitor = TailnetMonitor(api_key, tailnet)

    # Get network state
    print("\n🔍 Capturing Network State...")
    current_snapshot = monitor.get_current_state()

    print(
        f"Nodes Found: {current_snapshot.total_nodes} ({current_snapshot.online_nodes} Online)"
    )

    # Measure latency
    print("\n📊 Measuring Mesh Latency...")
    current_snapshot = monitor.measure_mesh_latency(current_snapshot)

    if current_snapshot.average_latency:
        print(f"Average Latency: {current_snapshot.average_latency:.2f}ms")

    # Generate visualization
    monitor.generate_interactive_graph(current_snapshot)


if __name__ == "__main__":
    run_interactive_monitor()
