"""
IDS Dashboard Module.

Professional monitoring dashboard for Raspberry Pi-based IDS system.
"""

from .app import create_dashboard_app
from .suricata import SuricataLogMonitor
from .elasticsearch import ElasticsearchMonitor
from .hardware import HardwareController
from .network import NetworkMonitor
from .ai_healing import AIHealingService
from .setup import OpenSearchSetup, TailnetSetup, setup_infrastructure
from .tailscale import TailscaleMonitor

__all__ = [
    "create_dashboard_app",
    "SuricataLogMonitor",
    "ElasticsearchMonitor",
    "HardwareController",
    "NetworkMonitor",
    "AIHealingService",
    "TailscaleMonitor",
    "TailnetSetup",
    "OpenSearchSetup",
    "setup_infrastructure",
]
