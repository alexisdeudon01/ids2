"""
Tailscale Network Monitoring Package.

This package provides SOLID-compliant components for Tailscale network monitoring:

- models: Data structures (DeviceState, NetworkSnapshot, HealthMetrics)
- interfaces: Abstract protocols for dependency inversion
- api_client: Tailscale API client implementation (uses Python tailscale library)
- connectivity: Network connectivity testing (via tailscale ping)
- visualizer: Interactive network visualization (Pyvis)
- monitor: High-level monitoring orchestrator

SOLID Principles Applied:
- S: Each module has a single responsibility
- O: Open for extension via protocols
- L: Implementations are substitutable
- I: Interfaces are focused and minimal
- D: High-level modules depend on abstractions

Example Usage:
    from ids.tailscale import TailnetMonitor

    monitor = TailnetMonitor(tailnet="example.com", api_key="tskey-api-xxx")
    snapshot = await monitor.capture_state(measure_latency=True)
    monitor.visualize(snapshot, "network.html")
"""

from .models import DeviceState, HealthMetrics, NetworkSnapshot
from .monitor import TailnetMonitor, run_monitor_async, run_monitor_interactive

__all__ = [
    # Models
    "DeviceState",
    "HealthMetrics",
    "NetworkSnapshot",
    # Monitor
    "TailnetMonitor",
    "run_monitor_async",
    "run_monitor_interactive",
]
