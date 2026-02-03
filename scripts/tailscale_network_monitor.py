#!/usr/bin/env python3
"""
Tailscale Network Monitoring & Visualization System
Role: Network Operations (NetOps) Specialist
"""

import requests
import getpass
import subprocess
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from pyvis.network import Network  # type: ignore

# --- 1. NETWORK REPRESENTATION DATASTRUCTURES ---

@dataclass
class DeviceState:
    """Point-in-time state of a Tailscale device"""
    device_id: str
    hostname: str
    tailscale_ip: str
    os: str
    status: str  # "online" or "offline"
    last_seen: str
    tags: List[str] = field(default_factory=list)
    latency: Optional[float] = None  # Populated by Monitor (ms)

@dataclass
class NetworkSnapshot:
    """Complete network state at a given timestamp"""
    timestamp: str
    total_nodes: int
    online_nodes: int
    average_latency: Optional[float] = None
    devices: List[DeviceState] = field(default_factory=list)


# --- 2. MONITORING & VISUALIZATION CLASS ---

class TailnetMonitor:
    """Monitors and visualizes a Tailscale mesh network"""
    
    def __init__(self, api_key: str, tailnet_name: str):
        self.api_key = api_key
        self.tailnet = tailnet_name
        self.base_url = f"https://api.tailscale.com/api/v2/tailnet/{tailnet_name}"
        self.headers = {"Authorization": f"Bearer {api_key}"}

    def get_current_state(self) -> NetworkSnapshot:
        """Fetches the current 'Truth' of the network from Tailscale API."""
        print("\n🔍 Fetching device list from Tailscale API...")
        res = requests.get(f"{self.base_url}/devices", headers=self.headers)
        res.raise_for_status()
        data = res.json().get('devices', [])
        
        devices = []
        for d in data:
            # Extract first IPv4 Tailscale address
            addresses = d.get('addresses', [])
            ts_ip = next((addr for addr in addresses if ':' not in addr), addresses[0] if addresses else 'N/A')
            
            devices.append(DeviceState(
                device_id=d['id'],
                hostname=d['hostname'],
                tailscale_ip=ts_ip,
                os=d.get('os', 'Unknown'),
                status="online" if d.get('online', False) else "offline",
                last_seen=d.get('lastSeen', 'N/A'),
                tags=d.get('tags', [])
            ))
        
        snapshot = NetworkSnapshot(
            timestamp=datetime.now().isoformat(),
            total_nodes=len(devices),
            online_nodes=sum(1 for d in devices if d.status == "online"),
            devices=devices
        )
        
        print(f"✅ Found {snapshot.total_nodes} nodes ({snapshot.online_nodes} online)")
        return snapshot

    def check_connectivity(self, target_ip: str, device_name: str) -> float:
        """Monitoring: Measures real-time latency to a specific node."""
        try:
            print(f"  📡 Pinging {device_name} ({target_ip})...", end=' ')
            # Use Tailscale CLI for accurate mesh measurement
            result = subprocess.run(
                ["tailscale", "ping", "-c", "1", target_ip],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # Parse latency from output (format: "pong from ... via ... in 12ms")
            output = result.stdout + result.stderr
            match = re.search(r'in (\d+\.?\d*)ms', output)
            if match:
                latency = float(match.group(1))
                print(f"✓ {latency}ms")
                return latency
            else:
                print("✗ No response")
                return -1.0
        except subprocess.TimeoutExpired:
            print("✗ Timeout")
            return -1.0
        except Exception as e:
            print(f"✗ Error: {e}")
            return -1.0

    def measure_network_latency(self, snapshot: NetworkSnapshot) -> NetworkSnapshot:
        """Measures latency to all online nodes and calculates average."""
        print("\n📊 Measuring network latency...")
        
        latencies = []
        for device in snapshot.devices:
            if device.status == "online" and device.tailscale_ip != 'N/A':
                latency = self.check_connectivity(device.tailscale_ip, device.hostname)
                device.latency = latency if latency > 0 else None
                if latency > 0:
                    latencies.append(latency)
        
        # Calculate average latency
        if latencies:
            snapshot.average_latency = sum(latencies) / len(latencies)
            print(f"\n✅ Average mesh latency: {snapshot.average_latency:.2f}ms")
        else:
            print("\n⚠️  No latency measurements available")
        
        return snapshot

    def generate_interactive_graph(self, snapshot: NetworkSnapshot):
        """Visualizes the network graph with latency-based node sizing."""
        print("\n🎨 Generating interactive network visualization...")
        
        net = Network(
            height="800px",
            width="100%",
            bgcolor="#1a1a1a",
            font_color="white",
            notebook=False
        )
        net.toggle_physics(True)
        net.set_options("""
        {
          "physics": {
            "barnesHut": {
              "gravitationalConstant": -30000,
              "centralGravity": 0.3,
              "springLength": 200
            }
          },
          "interaction": {
            "hover": true,
            "tooltipDelay": 100
          }
        }
        """)
        
        # Central Core Node
        net.add_node(
            "CORE",
            label=f"🌐 TAILNET\n{self.tailnet}",
            shape="diamond",
            color="#3498db",
            size=50,
            title="Tailscale Network Core"
        )

        # Calculate min/max latency for scaling
        valid_latencies = [d.latency for d in snapshot.devices if d.latency and d.latency > 0]
        min_lat = min(valid_latencies) if valid_latencies else 1
        max_lat = max(valid_latencies) if valid_latencies else 100

        for dev in snapshot.devices:
            # Color based on status
            if dev.status == "online":
                color = "#2ecc71"  # Green
            else:
                color = "#e74c3c"  # Red
            
            # Node size: Lower latency = LARGER node (inverted scale)
            if dev.latency and dev.latency > 0:
                # Inverse scaling: map latency to size (lower latency = bigger)
                # size ranges from 15 to 40
                if max_lat > min_lat:
                    normalized = (dev.latency - min_lat) / (max_lat - min_lat)
                    size = 40 - (normalized * 25)  # 40 for lowest, 15 for highest
                else:
                    size = 30
                latency_info = f"\n⚡ Latency: {dev.latency:.1f}ms"
            else:
                size = 15
                latency_info = "\n⚡ Latency: N/A"
            
            # Build tooltip with device info
            tags_str = ", ".join(dev.tags) if dev.tags else "None"
            title = f"""
<b>{dev.hostname}</b>
<hr>
<b>OS:</b> {dev.os}
<b>IP:</b> {dev.tailscale_ip}
<b>Status:</b> {dev.status.upper()}
<b>Tags:</b> {tags_str}
<b>Last Seen:</b> {dev.last_seen}{latency_info}
<hr>
<i>Click to view in Tailscale Console</i>
            """.strip()
            
            # Create console link (opens when node is clicked)
            console_url = f"https://login.tailscale.com/admin/machines/{dev.device_id}"
            
            net.add_node(
                dev.hostname,
                label=f"{dev.hostname}\n{dev.tailscale_ip}",
                title=title,
                color=color,
                shape="dot",
                size=size,
                url=console_url  # Clicking opens this URL
            )
            
            # Edge styling based on latency
            if dev.latency and dev.latency > 0:
                # Thicker edge = better latency
                edge_width = max(1, 5 - (dev.latency / 20))
                edge_color = "#2ecc71" if dev.latency < 50 else "#f39c12" if dev.latency < 100 else "#e74c3c"
            else:
                edge_width = 1
                edge_color = "#7f8c8d"
            
            net.add_edge("CORE", dev.hostname, width=edge_width, color=edge_color)

        # Add timestamp and stats to the graph
        stats_text = f"""
Network Snapshot: {snapshot.timestamp}
Total Nodes: {snapshot.total_nodes}
Online Nodes: {snapshot.online_nodes}
Average Latency: {f"{snapshot.average_latency:.2f}ms" if snapshot.average_latency else 'N/A'}
        """.strip()
        
        # Save to HTML
        output_file = "tailscale_network_map.html"
        net.show(output_file)
        
        print(f"✅ Interactive Network Health Map generated: '{output_file}'")
        print(f"\n📈 Network Statistics:")
        print(f"   Total Nodes: {snapshot.total_nodes}")
        print(f"   Online Nodes: {snapshot.online_nodes}")
        if snapshot.average_latency:
            print(f"   Average Latency: {snapshot.average_latency:.2f}ms")
        print(f"\n💡 Tip: Node size is inversely proportional to latency (bigger = faster)")
        print(f"💡 Click any node to open its Tailscale console page")


# --- 3. FINAL EXECUTION LOGIC ---

def run_manager():
    """Main entry point for the Tailscale Network Monitor"""
    print("=" * 60)
    print("🌐 TAILSCALE NETWORK MONITOR & VISUALIZER")
    print("=" * 60)
    
    # 1. Secure Inputs (API key never printed)
    api_key = getpass.getpass("\n🔑 Enter Tailscale API Key: ")
    tailnet = input("🏢 Enter Tailnet Name (e.g., example.com or user@github): ")
    
    if not api_key or not tailnet:
        print("❌ API key and tailnet name are required")
        return
    
    try:
        monitor = TailnetMonitor(api_key, tailnet)
        
        # 2. Get Network Representation
        current_snapshot = monitor.get_current_state()
        
        # 3. Monitoring: Measure latency to all online nodes
        current_snapshot = monitor.measure_network_latency(current_snapshot)
        
        # 4. Visualization: Generate interactive graph
        monitor.generate_interactive_graph(current_snapshot)
        
        print("\n✅ Monitoring cycle complete!")
        
    except requests.HTTPError as e:
        print(f"\n❌ API Error: {e}")
        print("   Check your API key and tailnet name")
    except FileNotFoundError:
        print("\n❌ Tailscale CLI not found. Install from https://tailscale.com/download")
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")


if __name__ == "__main__":
    run_manager()
