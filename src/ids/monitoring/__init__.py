"""Monitoring and visualization module for Tailscale mesh network."""

# Re-export from the new SOLID tailscale module
from ..tailscale import DeviceState, NetworkSnapshot, TailnetMonitor

__all__ = ["TailnetMonitor", "DeviceState", "NetworkSnapshot"]
