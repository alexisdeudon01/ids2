#!/usr/bin/env python3
import getpass
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import networkx as nx
import requests
from pyvis.network import Network  # type: ignore


@dataclass
class DeviceState:
    device_id: str
    hostname: str
    tailscale_ip: str
    tags: List[str]
    os: str
    status: str  # "online" or "offline"
    last_seen: str
    latency_ms: Optional[float] = None


@dataclass
class NetworkSnapshot:
    timestamp: str
    total_nodes: int
    online_nodes: int
    devices: List[DeviceState] = field(default_factory=list)


class TailnetMonitor:
    def __init__(self, api_key: str, tailnet_name: str) -> None:
        self.auth = (api_key, "")
        self.tailnet = tailnet_name
        self.base_url = f"https://api.tailscale.com/api/v2/tailnet/{tailnet_name}"

    def get_current_state(self) -> NetworkSnapshot:
        res = requests.get(f"{self.base_url}/devices", auth=self.auth, timeout=20)
        res.raise_for_status()
        data = res.json().get("devices", [])

        devices: List[DeviceState] = []
        for d in data:
            addresses = d.get("addresses") or []
            tailscale_ip = addresses[0] if addresses else "N/A"
            devices.append(
                DeviceState(
                    device_id=d["id"],
                    hostname=d.get("hostname", "unknown"),
                    tailscale_ip=tailscale_ip,
                    tags=d.get("tags", []),
                    os=d.get("os", "unknown"),
                    status="online" if d.get("online") else "offline",
                    last_seen=d.get("lastSeen", "N/A"),
                )
            )

        return NetworkSnapshot(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            total_nodes=len(devices),
            online_nodes=sum(1 for d in devices if d.status == "online"),
            devices=devices,
        )

    def ping_online_nodes(self, snapshot: NetworkSnapshot) -> float:
        latencies: List[float] = []
        for device in snapshot.devices:
            if device.status != "online" or device.tailscale_ip == "N/A":
                continue
            latency = self._tailscale_ping_latency(device.tailscale_ip)
            device.latency_ms = latency
            if latency is not None:
                latencies.append(latency)
        if not latencies:
            return -1.0
        return sum(latencies) / len(latencies)

    def generate_interactive_graph(self, snapshot: NetworkSnapshot, output_file: str) -> None:
        graph = nx.Graph()
        core_id = "TAILNET_CORE"
        graph.add_node(
            core_id,
            label=f"TAILNET\n{self.tailnet}",
            color="#3498db",
            shape="diamond",
            size=40,
        )

        device_links: Dict[str, str] = {}
        for device in snapshot.devices:
            node_id = device.device_id
            device_links[node_id] = (
                f"https://login.tailscale.com/admin/machines/{device.device_id}"
            )
            color = "#2ecc71" if device.status == "online" else "#e74c3c"
            size = self._size_from_latency(device.latency_ms)
            title = (
                f"OS: {device.os}\n"
                f"IP: {device.tailscale_ip}\n"
                f"Tags: {', '.join(device.tags) if device.tags else 'None'}\n"
                f"Last Seen: {device.last_seen}\n"
                f"Latency: {device.latency_ms if device.latency_ms is not None else 'N/A'} ms"
            )
            graph.add_node(
                node_id,
                label=device.hostname,
                title=title,
                color=color,
                shape="dot",
                size=size,
            )
            graph.add_edge(core_id, node_id, weight=1)

        net = Network(height="700px", width="100%", bgcolor="#1a1a1a", font_color="white")
        net.toggle_physics(True)
        net.from_nx(graph)

        html = net.generate_html()
        click_script = self._build_click_script(device_links)
        html = html.replace("</body>", f"{click_script}\n</body>")

        with open(output_file, "w", encoding="utf-8") as handle:
            handle.write(html)

    @staticmethod
    def _tailscale_ping_latency(target_ip: str) -> Optional[float]:
        try:
            result = subprocess.run(
                ["tailscale", "ping", "-c", "1", target_ip],
                check=True,
                text=True,
                capture_output=True,
                timeout=5,
            )
        except (subprocess.SubprocessError, FileNotFoundError):
            return None
        return TailnetMonitor._parse_latency(result.stdout)

    @staticmethod
    def _parse_latency(output: str) -> Optional[float]:
        match = re.search(r"in\s+([0-9.]+)ms", output)
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    @staticmethod
    def _size_from_latency(latency_ms: Optional[float]) -> int:
        if latency_ms is None or latency_ms <= 0:
            return 12
        # Lower latency = larger node, clamp between 12 and 42.
        size = int(max(12, min(42, 42 - (latency_ms / 5))))
        return size

    @staticmethod
    def _build_click_script(device_links: Dict[str, str]) -> str:
        payload = json.dumps(device_links)
        return f"""
<script>
  (function() {{
    var deviceLinks = {payload};
    if (typeof network !== "undefined") {{
      network.on("click", function(params) {{
        if (!params.nodes || params.nodes.length === 0) return;
        var nodeId = params.nodes[0];
        if (deviceLinks[nodeId]) {{
          alert("Tailscale Console:\\n" + deviceLinks[nodeId]);
        }}
      }});
    }}
  }})();
</script>
"""


def run_manager() -> None:
    api_key = getpass.getpass("Enter Tailscale API Key: ")
    tailnet = input("Enter Tailnet Name: ").strip()
    if not tailnet:
        print("Tailnet name is required.", file=sys.stderr)
        sys.exit(1)

    monitor = TailnetMonitor(api_key, tailnet)
    print("Capturing network state...")
    snapshot = monitor.get_current_state()
    avg_latency = monitor.ping_online_nodes(snapshot)

    nodes_info = f"Nodes: {snapshot.total_nodes} ({snapshot.online_nodes} online)"
    latency_info = f"Avg latency: {avg_latency:.2f} ms" if avg_latency >= 0 else "Avg latency: N/A"
    print(f"{nodes_info} | {latency_info}")

    output_file = os.path.abspath("network_health_map.html")
    monitor.generate_interactive_graph(snapshot, output_file)
    print(f"Interactive map generated: {output_file}")


if __name__ == "__main__":
    run_manager()
