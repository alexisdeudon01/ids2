"""
Network Visualization Implementation.

Single Responsibility: Only handles graph visualization.
"""

from __future__ import annotations

import json

from .interfaces import BaseVisualizer
from .models import NetworkSnapshot

# Optional dependency
try:
    from pyvis.network import Network  # type: ignore[import-not-found]

    PYVIS_AVAILABLE = True
except ImportError:
    PYVIS_AVAILABLE = False


class PyvisVisualizer(BaseVisualizer):
    """
    Network visualizer using Pyvis library.

    Single Responsibility: Only generates interactive HTML graph.
    Liskov Substitution: Can replace any BaseVisualizer.

    Visual design:
    - Node size inversely proportional to latency (faster = larger)
    - Color indicates status (green=online, red=offline, orange=unreachable)
    - Clicking nodes opens Tailscale Console
    """

    def __init__(
        self,
        height: str = "800px",
        width: str = "100%",
        bgcolor: str = "#0d1117",
        font_color: str = "#c9d1d9",
        min_node_size: int = 15,
        max_node_size: int = 45,
    ):
        """
        Initialize visualizer with styling options.

        Args:
            height: Graph height CSS
            width: Graph width CSS
            bgcolor: Background color
            font_color: Font color
            min_node_size: Minimum node size (high latency)
            max_node_size: Maximum node size (low latency)
        """
        if not PYVIS_AVAILABLE:
            raise ImportError("The 'pyvis' library is required for visualization. " "Install with: pip install pyvis")

        self.height = height
        self.width = width
        self.bgcolor = bgcolor
        self.font_color = font_color
        self.min_node_size = min_node_size
        self.max_node_size = max_node_size

    def generate(self, snapshot: NetworkSnapshot, output_path: str = "network_map.html") -> str:
        """
        Generate an interactive Pyvis graph.

        Args:
            snapshot: NetworkSnapshot to visualize
            output_path: Path to save the HTML file

        Returns:
            Path to the generated HTML file.
        """
        net = Network(
            height=self.height,
            width=self.width,
            bgcolor=self.bgcolor,
            font_color=self.font_color,
            directed=False,
        )

        self._configure_physics(net)
        self._add_core_node(net, snapshot)
        self._add_device_nodes(net, snapshot)

        # Save and inject click handlers
        net.write_html(output_path)
        self._inject_click_handlers(output_path, snapshot)
        self._inject_legend(output_path, snapshot)

        return output_path

    def _configure_physics(self, net: Network) -> None:
        """Configure graph physics and interaction."""
        net.toggle_physics(True)
        net.set_options("""
        {
            "nodes": {
                "borderWidth": 2,
                "font": {"size": 12, "face": "monospace"}
            },
            "edges": {
                "color": {"inherit": true},
                "smooth": {"type": "continuous"}
            },
            "physics": {
                "forceAtlas2Based": {
                    "gravitationalConstant": -50,
                    "centralGravity": 0.01,
                    "springLength": 180,
                    "springConstant": 0.08
                },
                "solver": "forceAtlas2Based"
            },
            "interaction": {
                "hover": true,
                "tooltipDelay": 100,
                "zoomView": true
            }
        }
        """)

    def _add_core_node(self, net: Network, snapshot: NetworkSnapshot) -> None:
        """Add the central tailnet node."""
        avg_lat = f"{snapshot.average_latency_ms:.1f}ms" if snapshot.average_latency_ms else "N/A"

        title = f"""
        <div style="font-family: monospace; padding: 8px;">
            <b style="font-size: 14px;">🌐 {snapshot.tailnet}</b><br><br>
            <b>Total Nodes:</b> {snapshot.total_nodes}<br>
            <b>Online:</b> {snapshot.online_nodes}<br>
            <b>Offline:</b> {snapshot.offline_nodes}<br>
            <b>Avg Latency:</b> {avg_lat}<br>
            <b>Snapshot:</b> {snapshot.timestamp}
        </div>
        """

        net.add_node(
            "TAILNET_CORE",
            label=f"⬡ {snapshot.tailnet}",
            title=title,
            shape="diamond",
            color="#58a6ff",
            size=50,
            font={"size": 14, "color": "#ffffff"},
        )

    def _add_device_nodes(self, net: Network, snapshot: NetworkSnapshot) -> None:
        """Add all device nodes with appropriate styling."""
        # Calculate latency range for size scaling
        latencies = [d.latency_ms for d in snapshot.devices if d.is_reachable]
        min_lat = min(latencies) if latencies else 0
        max_lat = max(latencies) if latencies else 100
        lat_range = max_lat - min_lat if max_lat > min_lat else 1

        for device in snapshot.devices:
            color, border = self._get_device_colors(device)
            size = self._calculate_node_size(device, min_lat, lat_range)
            title = self._build_device_tooltip(device)

            net.add_node(
                device.hostname,
                label=device.hostname,
                title=title,
                color={"background": color, "border": border},
                borderWidth=2,
                shape="dot",
                size=size,
            )

            # Edge to core
            edge_color = "#30363d" if not device.is_online else color
            edge_width = 1 if not device.is_online else 2
            net.add_edge("TAILNET_CORE", device.hostname, color=edge_color, width=edge_width)

    def _get_device_colors(self, device) -> tuple:
        """Determine node colors based on device state."""
        if not device.is_online:
            return "#f85149", "#da3633"  # Red - offline
        if device.latency_ms is None or device.latency_ms < 0:
            return "#f0883e", "#d47616"  # Orange - unreachable
        if device.latency_ms < 50:
            return "#3fb950", "#238636"  # Green - excellent
        if device.latency_ms < 150:
            return "#a371f7", "#8957e5"  # Purple - good
        return "#f0883e", "#d47616"  # Orange - slow

    def _calculate_node_size(self, device, min_lat: float, lat_range: float) -> float:
        """Calculate node size based on latency (lower = larger)."""
        if not device.is_reachable:
            return self.min_node_size

        # Inverse scale: lower latency = larger node
        normalized = 1 - ((device.latency_ms - min_lat) / lat_range) if lat_range > 0 else 0.5
        return self.min_node_size + (self.max_node_size - self.min_node_size) * normalized

    def _build_device_tooltip(self, device) -> str:
        """Build HTML tooltip for a device."""
        latency_str = f"{device.latency_ms:.1f}ms" if device.is_reachable else "N/A"
        tags_str = ", ".join(device.tags) if device.tags else "none"
        auth_str = "Yes" if device.authorized else "No"

        return f"""
        <div style="font-family: monospace; padding: 8px; max-width: 300px;">
            <b style="font-size: 14px;">{device.hostname}</b><br><br>
            <b>IP:</b> {device.tailscale_ip}<br>
            <b>OS:</b> {device.os}<br>
            <b>Status:</b> {device.status}<br>
            <b>Latency:</b> {latency_str}<br>
            <b>Tags:</b> {tags_str}<br>
            <b>Authorized:</b> {auth_str}<br>
            <b>Last Seen:</b> {device.last_seen}<br><br>
            <a href="{device.console_url}" target="_blank"
               style="color: #58a6ff; text-decoration: none;">
               🔗 Open in Tailscale Console
            </a>
        </div>
        """

    def _inject_click_handlers(self, html_file: str, snapshot: NetworkSnapshot) -> None:
        """Inject JavaScript click handlers to open device console."""
        device_urls = {d.hostname: d.console_url for d in snapshot.devices}

        js_code = f"""
        <script>
        (function() {{
            const deviceUrls = {json.dumps(device_urls)};

            if (typeof network !== 'undefined') {{
                network.on('doubleClick', function(params) {{
                    if (params.nodes.length > 0) {{
                        const nodeId = params.nodes[0];
                        if (nodeId !== 'TAILNET_CORE' && deviceUrls[nodeId]) {{
                            window.open(deviceUrls[nodeId], '_blank');
                        }}
                    }}
                }});
            }}
        }})();
        </script>
        """

        with open(html_file, "r", encoding="utf-8") as f:
            content = f.read()

        content = content.replace("</body>", f"{js_code}\n</body>")

        with open(html_file, "w", encoding="utf-8") as f:
            f.write(content)

    def _inject_legend(self, html_file: str, snapshot: NetworkSnapshot) -> None:
        """Inject a legend into the HTML."""
        avg_lat = f"{snapshot.average_latency_ms:.1f}ms" if snapshot.average_latency_ms else "N/A"

        legend = f"""
        <div style="position:absolute;top:10px;left:10px;background:#161b22;
             padding:15px;border-radius:8px;border:1px solid #30363d;
             font-family:monospace;font-size:12px;color:#c9d1d9;z-index:1000;">
            <b style="font-size:14px;">Network Health Map</b><br><br>
            <b>Snapshot:</b> {snapshot.timestamp}<br>
            <b>Nodes:</b> {snapshot.online_nodes}/{snapshot.total_nodes} online<br>
            <b>Avg Latency:</b> {avg_lat}<br><br>
            <span style="color:#3fb950;">●</span> Online (fast)<br>
            <span style="color:#a371f7;">●</span> Online (medium)<br>
            <span style="color:#f0883e;">●</span> Online (slow/unreachable)<br>
            <span style="color:#f85149;">●</span> Offline<br><br>
            <i>Larger nodes = lower latency</i><br>
            <i>Double-click to open console</i>
        </div>
        """

        with open(html_file, "r", encoding="utf-8") as f:
            content = f.read()

        content = content.replace("<body>", f"<body>{legend}")

        with open(html_file, "w", encoding="utf-8") as f:
            f.write(content)
