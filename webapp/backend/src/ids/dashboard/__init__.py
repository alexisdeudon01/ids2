"""
IDS Dashboard Module.

Professional monitoring dashboard for Raspberry Pi-based IDS system.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .ai_healing import AIHealingService as AIHealingService
    from .app import create_dashboard_app as create_dashboard_app
    from .elasticsearch import ElasticsearchMonitor as ElasticsearchMonitor
    from .hardware import HardwareController as HardwareController
    from .network import NetworkMonitor as NetworkMonitor
    from .setup import OpenSearchSetup as OpenSearchSetup
    from .setup import TailnetSetup as TailnetSetup
    from .setup import setup_infrastructure as setup_infrastructure
    from .suricata import SuricataLogMonitor as SuricataLogMonitor
    from .tailscale import TailscaleMonitor as TailscaleMonitor

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


def __getattr__(name: str):  # pragma: no cover
    """
    Lazy imports to keep `import ids.dashboard` lightweight.

    This allows utility modules (like permission checks) to run even if optional
    runtime dependencies (FastAPI, Elasticsearch client, etc.) are not installed.
    """

    if name == "create_dashboard_app":
        from .app import create_dashboard_app

        return create_dashboard_app
    if name == "SuricataLogMonitor":
        from .suricata import SuricataLogMonitor

        return SuricataLogMonitor
    if name == "ElasticsearchMonitor":
        from .elasticsearch import ElasticsearchMonitor

        return ElasticsearchMonitor
    if name == "HardwareController":
        from .hardware import HardwareController

        return HardwareController
    if name == "NetworkMonitor":
        from .network import NetworkMonitor

        return NetworkMonitor
    if name == "AIHealingService":
        from .ai_healing import AIHealingService

        return AIHealingService
    if name == "TailscaleMonitor":
        from .tailscale import TailscaleMonitor

        return TailscaleMonitor
    if name in {"TailnetSetup", "OpenSearchSetup", "setup_infrastructure"}:
        from .setup import OpenSearchSetup, TailnetSetup, setup_infrastructure

        return {
            "TailnetSetup": TailnetSetup,
            "OpenSearchSetup": OpenSearchSetup,
            "setup_infrastructure": setup_infrastructure,
        }[name]
    raise AttributeError(name)
