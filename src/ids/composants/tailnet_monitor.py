"""
Tailscale Mesh Network Monitoring and Visualization System.

This module provides:
- NetworkSnapshot: Point-in-time view of all devices
- TailnetMonitor: Monitoring logic with latency measurement
- Interactive Pyvis graph visualization
"""

import asyncio
import getpass
import subprocess
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import requests  # type: ignore[import-untyped]
from pyvis.network import Network  # type: ignore[import-not-found]


@dataclass
class DeviceState:
    """Represents the state of a single Tailscale device."""

    device_id: str
    hostname: str
    tailscale_ip: str
    os: str
    status: str  # "online" or "offline"
    last_seen: str
    tags: list[str] = field(default_factory=list)
    latency_ms: Optional[float] = None  # Populated by monitor


@dataclass
class NetworkSnapshot:
    """Point-in-time view of the entire Tailscale mesh network."""

    timestamp: str
    tailnet: str
    total_nodes: int
    online_nodes: int
    average_latency_ms: Optional[float] = None
    devices: list[DeviceState] = field(default_factory=list)


class TailnetMonitor:
    """
    Monitors a Tailscale mesh network.

    Provides:
    - Device discovery via Tailscale API
    - Latency measurement via tailscale ping
    - Interactive graph visualization with Pyvis
    """

    def __init__(self, api_key: str, tailnet_name: str):
        """
        Initialize the monitor.

        Args:
            api_key: Tailscale API key (never printed to console)
            tailnet_name: Name of the tailnet (e.g., "example.com" or "yourname.github")
        """
        self._auth = (api_key, "")
        self.tailnet = tailnet_name
        self.base_url = f"https://api.tailscale.com/api/v2/tailnet/{tailnet_name}"

    def get_current_state(self) -> NetworkSnapshot:
        """
        Fetch the current state of the network from Tailscale API.

        Returns:
            NetworkSnapshot with all devices and their states.
        """
        res = requests.get(f"{self.base_url}/devices", auth=self._auth, timeout=30)
        res.raise_for_status()
        data = res.json().get("devices", [])

        devices = []
        for d in data:
            addresses = d.get("addresses", [])
            devices.append(
                DeviceState(
                    device_id=d.get("id", ""),
                    hostname=d.get("hostname", "unknown"),
                    tailscale_ip=addresses[0] if addresses else "N/A",
                    os=d.get("os", "unknown"),
                    status="online" if d.get("online") else "offline",
                    last_seen=d.get("lastSeen", "N/A"),
                    tags=d.get("tags", []),
                )
            )

        return NetworkSnapshot(
            timestamp=datetime.now().isoformat(),
            tailnet=self.tailnet,
            total_nodes=len(devices),
            online_nodes=sum(1 for dev in devices if dev.status == "online"),
            devices=devices,
        )

    def measure_latency(self, target_ip: str, count: int = 3) -> Optional[float]:
        """
        Measure latency to a specific node using tailscale ping.

        Args:
            target_ip: Tailscale IP of the target device
            count: Number of pings to send

        Returns:
            Average latency in milliseconds, or None if unreachable.
        """
        try:
            output = subprocess.check_output(
                ["tailscale", "ping", "-c", str(count), target_ip],
                timeout=15,
                stderr=subprocess.STDOUT,
            ).decode()

            # Extract latency values from output (e.g., "pong from ... in 12.34ms")
            latencies = re.findall(r"in\s+([\d.]+)\s*ms", output, re.IGNORECASE)
            if latencies:
                return sum(float(lat) for lat in latencies) / len(latencies)
        except subprocess.TimeoutExpired:
            pass
        except subprocess.CalledProcessError:
            pass
        except FileNotFoundError:
            print("WARN: tailscale CLI not found, skipping ping")

        return None

    def measure_all_latencies(self, snapshot: NetworkSnapshot) -> NetworkSnapshot:
        """
        Measure latency to all online devices and update the snapshot.

        Args:
            snapshot: NetworkSnapshot to update

        Returns:
            Updated NetworkSnapshot with latency values.
        """
        latencies = []
        for dev in snapshot.devices:
            if dev.status == "online" and dev.tailscale_ip != "N/A":
                print(f"  Pinging {dev.hostname} ({dev.tailscale_ip})...")
                lat = self.measure_latency(dev.tailscale_ip)
                dev.latency_ms = lat
                if lat is not None:
                    latencies.append(lat)

        if latencies:
            snapshot.average_latency_ms = sum(latencies) / len(latencies)

        return snapshot

    def generate_interactive_graph(
        self,
        snapshot: NetworkSnapshot,
        output_path: str = "tailnet_health_map.html",
    ) -> str:
        """
        Generate an interactive Pyvis graph of the network.

        Visual logic:
        - Node size scales inversely with latency (lower latency = larger node)
        - Green = online, Red = offline
        - Clicking a node shows device details and console link

        Args:
            snapshot: NetworkSnapshot to visualize
            output_path: Path to save the HTML file

        Returns:
            Path to the generated HTML file.
        """
        net = Network(
            height="800px",
            width="100%",
            bgcolor="#0d1117",
            font_color="#c9d1d9",
            directed=False,
        )
        net.toggle_physics(True)
        net.set_options(
            """
        {
            "nodes": {
                "borderWidth": 2,
                "borderWidthSelected": 4,
                "font": {"size": 14}
            },
            "edges": {
                "color": {"inherit": true},
                "smooth": {"type": "continuous"}
            },
            "physics": {
                "barnesHut": {
                    "gravitationalConstant": -8000,
                    "springLength": 150
                }
            },
            "interaction": {
                "hover": true,
                "tooltipDelay": 100
            }
        }
        """
        )

        # Central core node representing the tailnet
        net.add_node(
            "TAILNET_CORE",
            label=f"🌐 {snapshot.tailnet}",
            shape="diamond",
            color="#58a6ff",
            size=50,
            title=f"Tailnet: {snapshot.tailnet}\nTotal: {snapshot.total_nodes} nodes\nOnline: {snapshot.online_nodes}",
        )

        # Calculate size range based on latencies
        latencies = [
            d.latency_ms for d in snapshot.devices if d.latency_ms is not None
        ]
        max_lat = max(latencies) if latencies else 100
        min_lat = min(latencies) if latencies else 0

        for dev in snapshot.devices:
            # Color based on status
            if dev.status == "online":
                color = "#238636"  # Green
            else:
                color = "#da3633"  # Red

            # Size based on latency (lower = larger, range 15-40)
            if dev.latency_ms is not None and max_lat > min_lat:
                # Invert: lower latency = larger size
                normalized = (max_lat - dev.latency_ms) / (max_lat - min_lat)
                size = 15 + normalized * 25
            elif dev.status == "online":
                size = 25  # Default for online without latency
            else:
                size = 15  # Smaller for offline

            # Build tooltip with device info
            latency_str = (
                f"{dev.latency_ms:.2f} ms" if dev.latency_ms is not None else "N/A"
            )
            tags_str = ", ".join(dev.tags) if dev.tags else "none"
            console_url = f"https://login.tailscale.com/admin/machines/{dev.device_id}"

            title = f"""
<b>{dev.hostname}</b><br>
<hr>
<b>IP:</b> {dev.tailscale_ip}<br>
<b>OS:</b> {dev.os}<br>
<b>Status:</b> {dev.status}<br>
<b>Latency:</b> {latency_str}<br>
<b>Tags:</b> {tags_str}<br>
<b>Last Seen:</b> {dev.last_seen}<br>
<hr>
<a href="{console_url}" target="_blank">Open in Tailscale Console</a>
"""

            net.add_node(
                dev.device_id or dev.hostname,
                label=dev.hostname,
                title=title,
                color=color,
                size=size,
                shape="dot",
            )

            # Edge to core
            edge_color = "#30363d" if dev.status == "offline" else "#238636"
            net.add_edge(
                "TAILNET_CORE",
                dev.device_id or dev.hostname,
                color=edge_color,
                width=1 if dev.status == "offline" else 2,
            )

        # Add legend as a note
        latency_text = f"{snapshot.average_latency_ms:.2f} ms" if snapshot.average_latency_ms else "N/A"
        legend_html = f"""
        <div style="position:absolute;top:10px;left:10px;background:#161b22;padding:15px;border-radius:8px;border:1px solid #30363d;">
            <b style="color:#c9d1d9;">Network Health Map</b><br>
            <small style="color:#8b949e;">
                Snapshot: {snapshot.timestamp}<br>
                Avg Latency: {latency_text}<br>
                <span style="color:#238636;">●</span> Online &nbsp;
                <span style="color:#da3633;">●</span> Offline<br>
                <i>Larger nodes = lower latency</i>
            </small>
        </div>
        """

        net.save_graph(output_path)

        # Inject legend into HTML
        with open(output_path, "r") as f:
            html = f.read()
        html = html.replace("<body>", f"<body>{legend_html}")
        with open(output_path, "w") as f:
            f.write(html)

        return output_path


async def run_monitor_async(api_key: str, tailnet: str) -> NetworkSnapshot:
    """
    Async wrapper for running the monitor.

    Args:
        api_key: Tailscale API key
        tailnet: Tailnet name

    Returns:
        NetworkSnapshot with latencies measured.
    """
    monitor = TailnetMonitor(api_key, tailnet)

    print("\n🔍 Capturing Network State...")
    snapshot = monitor.get_current_state()
    print(
        f"   Nodes Found: {snapshot.total_nodes} ({snapshot.online_nodes} Online)"
    )

    print("\n📡 Measuring Latencies...")
    snapshot = monitor.measure_all_latencies(snapshot)
    if snapshot.average_latency_ms:
        print(f"   Average Latency: {snapshot.average_latency_ms:.2f} ms")

    print("\n🌍 Generating Interactive Graph...")
    output = monitor.generate_interactive_graph(snapshot)
    print(f"   Saved to: {output}")

    return snapshot


def run_monitor_interactive() -> None:
    """
    Run the monitor interactively, prompting for credentials.

    Security: API key is collected via getpass and never printed.
    """
    print("=" * 60)
    print("  Tailscale Mesh Network Monitor")
    print("=" * 60)

    # Secure input - never printed
    api_key = getpass.getpass("Enter Tailscale API Key: ")
    tailnet = input("Enter Tailnet Name: ")

    if not api_key or not tailnet:
        print("ERROR: API key and tailnet name are required.")
        return

    asyncio.run(run_monitor_async(api_key, tailnet))


if __name__ == "__main__":
    run_monitor_interactive()
