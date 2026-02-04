"""
Tailscale Mesh Network Representation and Monitoring System.

This module provides:
- NetworkSnapshot: Point-in-time view of all devices
- TailnetMonitor: Monitoring and visualization of the mesh network
- Interactive Pyvis graph with latency-based node sizing
"""

from __future__ import annotations

import asyncio
import getpass
import json
import subprocess
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any

import requests

try:
    from pyvis.network import Network  # type: ignore[import-not-found]
    PYVIS_AVAILABLE = True
except ImportError:
    PYVIS_AVAILABLE = False

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False


# --- 1. NETWORK REPRESENTATION DATASTRUCTURES ---


@dataclass
class DeviceState:
    """Represents a single Tailscale device's state."""

    device_id: str
    hostname: str
    tailscale_ip: str
    os: str
    status: str  # "online" or "offline"
    last_seen: str
    tags: List[str] = field(default_factory=list)
    latency_ms: Optional[float] = None  # Populated by Monitor
    authorized: bool = True
    client_version: str = ""

    @property
    def console_url(self) -> str:
        """Returns the Tailscale Device Console URL for this device."""
        return f"https://login.tailscale.com/admin/machines/{self.device_id}"

    @property
    def is_online(self) -> bool:
        return self.status == "online"


@dataclass
class NetworkSnapshot:
    """
    Point-in-time snapshot of the entire Tailscale mesh network.
    
    Captures all devices, their IPs, tags, and connectivity status.
    """

    timestamp: str
    tailnet: str
    total_nodes: int
    online_nodes: int
    offline_nodes: int
    average_latency_ms: Optional[float] = None
    devices: List[DeviceState] = field(default_factory=list)

    @classmethod
    def create(cls, tailnet: str, devices: List[DeviceState]) -> "NetworkSnapshot":
        """Factory method to create a snapshot from a list of devices."""
        online = [d for d in devices if d.is_online]
        latencies = [d.latency_ms for d in online if d.latency_ms is not None and d.latency_ms >= 0]
        avg_latency = sum(latencies) / len(latencies) if latencies else None

        return cls(
            timestamp=datetime.now().isoformat(),
            tailnet=tailnet,
            total_nodes=len(devices),
            online_nodes=len(online),
            offline_nodes=len(devices) - len(online),
            average_latency_ms=avg_latency,
            devices=devices,
        )

    def get_device_by_ip(self, ip: str) -> Optional[DeviceState]:
        """Find a device by its Tailscale IP."""
        for device in self.devices:
            if device.tailscale_ip == ip:
                return device
        return None

    def get_online_devices(self) -> List[DeviceState]:
        """Return only online devices."""
        return [d for d in self.devices if d.is_online]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize snapshot to dictionary."""
        return {
            "timestamp": self.timestamp,
            "tailnet": self.tailnet,
            "total_nodes": self.total_nodes,
            "online_nodes": self.online_nodes,
            "offline_nodes": self.offline_nodes,
            "average_latency_ms": self.average_latency_ms,
            "devices": [
                {
                    "device_id": d.device_id,
                    "hostname": d.hostname,
                    "tailscale_ip": d.tailscale_ip,
                    "os": d.os,
                    "status": d.status,
                    "last_seen": d.last_seen,
                    "tags": d.tags,
                    "latency_ms": d.latency_ms,
                    "authorized": d.authorized,
                    "console_url": d.console_url,
                }
                for d in self.devices
            ],
        }


# --- 2. MONITORING & VISUALIZATION CLASS ---


class TailnetMonitor:
    """
    Monitors and visualizes a Tailscale mesh network.
    
    Features:
    - Fetch current network state from Tailscale API
    - Measure latency to all online nodes via tailscale ping
    - Generate interactive Pyvis visualization
    - Node sizes scaled by latency (lower = larger)
    """

    def __init__(self, api_key: str, tailnet_name: str):
        """
        Initialize the monitor.
        
        Args:
            api_key: Tailscale API key (tskey-api-...)
            tailnet_name: Tailnet name (e.g., "example.com" or "yourname.github")
        """
        self.auth = (api_key, "")
        self.tailnet = tailnet_name
        # API URL format: https://api.tailscale.com/api/v2/tailnet/{tailnet}/devices
        self.base_url = f"https://api.tailscale.com/api/v2/tailnet/{tailnet_name}"

    def get_current_state(self, measure_latency: bool = True) -> NetworkSnapshot:
        """
        Fetches the current state of the network from Tailscale API.
        
        Args:
            measure_latency: If True, ping all online nodes to measure latency
            
        Returns:
            NetworkSnapshot with all devices and their states
        """
        res = requests.get(f"{self.base_url}/devices", auth=self.auth, timeout=30)
        res.raise_for_status()
        data = res.json().get("devices", [])

        devices: List[DeviceState] = []
        for d in data:
            addresses = d.get("addresses", [])
            device = DeviceState(
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
            devices.append(device)

        # Measure latency for online devices
        if measure_latency:
            self._measure_all_latencies(devices)

        return NetworkSnapshot.create(self.tailnet, devices)

    def _measure_all_latencies(self, devices: List[DeviceState]) -> None:
        """Measure latency to all online devices."""
        online_devices = [d for d in devices if d.is_online and d.tailscale_ip]
        print(f"📡 Measuring latency to {len(online_devices)} online nodes...")

        for device in online_devices:
            latency = self.check_connectivity(device.tailscale_ip)
            device.latency_ms = latency
            status = f"{latency:.1f}ms" if latency >= 0 else "unreachable"
            print(f"  • {device.hostname}: {status}")

    def check_connectivity(self, target_ip: str, count: int = 3) -> float:
        """
        Measures real-time latency to a specific node using tailscale ping.
        
        Args:
            target_ip: Tailscale IP address to ping
            count: Number of pings to average
            
        Returns:
            Average latency in milliseconds, or -1.0 if unreachable
        """
        try:
            output = subprocess.check_output(
                ["tailscale", "ping", "-c", str(count), target_ip],
                timeout=15,
                stderr=subprocess.STDOUT,
            ).decode()

            # Parse latency from output like "pong from hostname (100.x.x.x) via DERP(fra) in 45ms"
            latencies = re.findall(r"in\s+([\d.]+)ms", output)
            if latencies:
                return sum(float(lat) for lat in latencies) / len(latencies)

        except subprocess.TimeoutExpired:
            return -1.0
        except subprocess.CalledProcessError:
            return -1.0
        except Exception:
            return -1.0

        return -1.0

    def calculate_mesh_health(self, snapshot: NetworkSnapshot) -> Dict[str, Any]:
        """
        Calculate overall mesh health metrics.
        
        Returns:
            Dictionary with health metrics
        """
        online = snapshot.get_online_devices()
        latencies = [d.latency_ms for d in online if d.latency_ms is not None and d.latency_ms >= 0]

        return {
            "total_nodes": snapshot.total_nodes,
            "online_nodes": snapshot.online_nodes,
            "offline_nodes": snapshot.offline_nodes,
            "availability_percent": (snapshot.online_nodes / snapshot.total_nodes * 100) if snapshot.total_nodes > 0 else 0,
            "average_latency_ms": sum(latencies) / len(latencies) if latencies else None,
            "max_latency_ms": max(latencies) if latencies else None,
            "min_latency_ms": min(latencies) if latencies else None,
            "reachable_nodes": len(latencies),
            "unreachable_online_nodes": len(online) - len(latencies),
        }

    def generate_interactive_graph(
        self,
        snapshot: NetworkSnapshot,
        output_file: str = "network_health_map.html",
        min_node_size: int = 15,
        max_node_size: int = 50,
    ) -> str:
        """
        Generate an interactive Pyvis graph of the network.
        
        Node sizes are scaled based on latency (lower latency = larger node).
        Clicking a node shows device info and console link.
        
        Args:
            snapshot: NetworkSnapshot to visualize
            output_file: Output HTML file path
            min_node_size: Minimum node size for high-latency nodes
            max_node_size: Maximum node size for low-latency nodes
            
        Returns:
            Path to the generated HTML file
        """
        if not PYVIS_AVAILABLE:
            raise ImportError("pyvis is required for visualization. Install with: pip install pyvis")

        net = Network(
            height="800px",
            width="100%",
            bgcolor="#0d1117",
            font_color="#c9d1d9",
            directed=False,
        )
        net.toggle_physics(True)
        net.set_options("""
        {
            "nodes": {
                "font": {"size": 14, "face": "monospace"}
            },
            "edges": {
                "color": {"inherit": true},
                "smooth": {"type": "continuous"}
            },
            "physics": {
                "forceAtlas2Based": {
                    "gravitationalConstant": -50,
                    "centralGravity": 0.01,
                    "springLength": 200,
                    "springConstant": 0.08
                },
                "solver": "forceAtlas2Based"
            },
            "interaction": {
                "hover": true,
                "tooltipDelay": 100
            }
        }
        """)

        # Add central Tailnet node
        core_title = f"""
        <b>TAILNET: {snapshot.tailnet}</b><br>
        Total Nodes: {snapshot.total_nodes}<br>
        Online: {snapshot.online_nodes}<br>
        Offline: {snapshot.offline_nodes}<br>
        Avg Latency: {snapshot.average_latency_ms:.1f}ms
        """ if snapshot.average_latency_ms else f"""
        <b>TAILNET: {snapshot.tailnet}</b><br>
        Total Nodes: {snapshot.total_nodes}<br>
        Online: {snapshot.online_nodes}<br>
        Offline: {snapshot.offline_nodes}
        """

        net.add_node(
            "CORE",
            label=f"⬡ {snapshot.tailnet}",
            title=core_title,
            shape="diamond",
            color="#58a6ff",
            size=45,
            font={"size": 16, "color": "#ffffff"},
        )

        # Calculate latency range for scaling
        latencies = [
            d.latency_ms for d in snapshot.devices
            if d.latency_ms is not None and d.latency_ms >= 0
        ]
        if latencies:
            min_lat = min(latencies)
            max_lat = max(latencies)
            lat_range = max_lat - min_lat if max_lat > min_lat else 1
        else:
            min_lat, max_lat, lat_range = 0, 100, 100

        # Add device nodes
        for dev in snapshot.devices:
            # Color based on status
            if not dev.is_online:
                color = "#f85149"  # Red for offline
                border_color = "#da3633"
            elif dev.latency_ms is None or dev.latency_ms < 0:
                color = "#f0883e"  # Orange for unreachable
                border_color = "#d47616"
            elif dev.latency_ms < 50:
                color = "#3fb950"  # Green for low latency
                border_color = "#238636"
            elif dev.latency_ms < 150:
                color = "#a371f7"  # Purple for medium latency
                border_color = "#8957e5"
            else:
                color = "#f0883e"  # Orange for high latency
                border_color = "#d47616"

            # Scale node size based on latency (inversely)
            if dev.latency_ms is not None and dev.latency_ms >= 0:
                # Lower latency = larger node
                normalized = 1 - ((dev.latency_ms - min_lat) / lat_range) if lat_range > 0 else 0.5
                node_size = min_node_size + (max_node_size - min_node_size) * normalized
            else:
                node_size = min_node_size

            # Build tooltip with device info and console link
            latency_str = f"{dev.latency_ms:.1f}ms" if dev.latency_ms and dev.latency_ms >= 0 else "N/A"
            tags_str = ", ".join(dev.tags) if dev.tags else "none"

            title = f"""
            <div style="font-family: monospace; padding: 8px;">
                <b style="font-size: 14px;">{dev.hostname}</b><br><br>
                <b>IP:</b> {dev.tailscale_ip}<br>
                <b>OS:</b> {dev.os}<br>
                <b>Status:</b> {dev.status}<br>
                <b>Latency:</b> {latency_str}<br>
                <b>Tags:</b> {tags_str}<br>
                <b>Last Seen:</b> {dev.last_seen}<br>
                <b>Authorized:</b> {'Yes' if dev.authorized else 'No'}<br><br>
                <a href="{dev.console_url}" target="_blank" 
                   style="color: #58a6ff; text-decoration: none;">
                   🔗 Open in Tailscale Console
                </a>
            </div>
            """

            net.add_node(
                dev.hostname,
                label=dev.hostname,
                title=title,
                color={"background": color, "border": border_color},
                borderWidth=2,
                shape="dot",
                size=node_size,
            )

            # Edge from core to device
            edge_color = color if dev.is_online else "#484f58"
            net.add_edge("CORE", dev.hostname, color=edge_color, width=1.5)

        # Generate HTML
        net.write_html(output_file)

        # Inject custom JavaScript for click handling
        self._inject_click_handler(output_file, snapshot)

        print(f"🌍 Interactive Network Health Map generated: {output_file}")
        return output_file

    def _inject_click_handler(self, html_file: str, snapshot: NetworkSnapshot) -> None:
        """Inject JavaScript to handle node clicks and open device console."""
        # Build device ID mapping
        device_map = {d.hostname: d.console_url for d in snapshot.devices}

        js_code = f"""
        <script>
        // Device console URL mapping
        const deviceUrls = {json.dumps(device_map)};
        
        // Wait for network to be ready
        network.on("click", function(params) {{
            if (params.nodes.length > 0) {{
                const nodeId = params.nodes[0];
                if (nodeId !== "CORE" && deviceUrls[nodeId]) {{
                    // Show confirmation before opening
                    if (confirm("Open Tailscale Console for " + nodeId + "?")) {{
                        window.open(deviceUrls[nodeId], "_blank");
                    }}
                }}
            }}
        }});
        
        // Double-click to open directly
        network.on("doubleClick", function(params) {{
            if (params.nodes.length > 0) {{
                const nodeId = params.nodes[0];
                if (nodeId !== "CORE" && deviceUrls[nodeId]) {{
                    window.open(deviceUrls[nodeId], "_blank");
                }}
            }}
        }});
        </script>
        """

        with open(html_file, "r") as f:
            content = f.read()

        # Insert before closing body tag
        content = content.replace("</body>", f"{js_code}\n</body>")

        with open(html_file, "w") as f:
            f.write(content)


# --- 3. STANDALONE EXECUTION ---


def run_monitor() -> None:
    """Interactive CLI to run the Tailnet monitor."""
    print("=" * 60)
    print("  🌐 TAILSCALE MESH NETWORK MONITOR")
    print("=" * 60)
    print()

    # Secure API key input (never printed)
    api_key = getpass.getpass("🔑 Enter Tailscale API Key: ")
    if not api_key:
        print("❌ API key is required.")
        return

    tailnet = input("📡 Enter Tailnet Name: ").strip()
    if not tailnet:
        print("❌ Tailnet name is required.")
        return

    print()
    monitor = TailnetMonitor(api_key, tailnet)

    # Fetch network state
    print("🔍 Capturing Network State...")
    try:
        snapshot = monitor.get_current_state(measure_latency=True)
    except requests.exceptions.HTTPError as e:
        print(f"❌ API Error: {e}")
        return
    except Exception as e:
        print(f"❌ Error: {e}")
        return

    # Display summary
    print()
    print("=" * 60)
    print(f"  📊 NETWORK SNAPSHOT - {snapshot.timestamp}")
    print("=" * 60)
    print(f"  Tailnet:        {snapshot.tailnet}")
    print(f"  Total Nodes:    {snapshot.total_nodes}")
    print(f"  Online:         {snapshot.online_nodes}")
    print(f"  Offline:        {snapshot.offline_nodes}")
    if snapshot.average_latency_ms:
        print(f"  Avg Latency:    {snapshot.average_latency_ms:.1f}ms")
    print()

    # Health metrics
    health = monitor.calculate_mesh_health(snapshot)
    print(f"  📈 Mesh Health:")
    print(f"     Availability:  {health['availability_percent']:.1f}%")
    if health['average_latency_ms']:
        print(f"     Latency Range: {health['min_latency_ms']:.1f}ms - {health['max_latency_ms']:.1f}ms")
    print()

    # List devices
    print("  📋 Devices:")
    for dev in snapshot.devices:
        status_icon = "🟢" if dev.is_online else "🔴"
        latency_str = f"{dev.latency_ms:.1f}ms" if dev.latency_ms and dev.latency_ms >= 0 else "N/A"
        print(f"     {status_icon} {dev.hostname:<20} {dev.tailscale_ip:<16} {latency_str}")
    print()

    # Generate visualization
    print("🎨 Generating interactive visualization...")
    output_file = monitor.generate_interactive_graph(snapshot)
    print()
    print(f"✅ Done! Open {output_file} in your browser.")


async def check_tailscale_connectivity_async(
    api_key: str,
    tailnet: str,
    target_ip: str,
) -> bool:
    """
    Async helper to check Tailscale connectivity (for use in CI/CD).
    
    Args:
        api_key: Tailscale API key
        tailnet: Tailnet name
        target_ip: Target device IP to verify
        
    Returns:
        True if device is found and authorized
    """
    monitor = TailnetMonitor(api_key, tailnet)
    snapshot = monitor.get_current_state(measure_latency=False)

    device = snapshot.get_device_by_ip(target_ip)
    if not device:
        print(f"❌ Device not found for IP: {target_ip}")
        return False

    if not device.authorized:
        print(f"❌ Device not authorized: {device.hostname}")
        return False

    print(f"✅ Device found: {device.hostname} ({target_ip})")

    # Ping test
    latency = monitor.check_connectivity(target_ip)
    if latency < 0:
        print(f"⚠️ Device unreachable via ping")
        return False

    print(f"✅ Ping OK: {latency:.1f}ms")
    return True


if __name__ == "__main__":
    run_monitor()
