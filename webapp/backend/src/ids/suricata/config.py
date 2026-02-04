"""
Generation minimale de configuration Suricata.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from pathlib import Path

    from ..interfaces import GestionnaireConfig


def build_suricata_config(
    interface: str,
    log_path: str,
    home_net: str = "192.168.0.0/16",
) -> dict[str, Any]:
    return {
        "vars": {"address-groups": {"HOME_NET": home_net}},
        "af-packet": [{"interface": interface}],
        "outputs": [{"eve-log": {"enabled": True, "filename": log_path}}],
    }


def generer_config_suricata(
    config: GestionnaireConfig | None,
    dest_path: Path,
) -> None:
    """Genere une configuration Suricata minimale."""
    home_net = "192.168.0.0/16"
    eve_log_path = "/mnt/ram_logs/eve.json"
    interface = "eth0"
    if config:
        home_net = config.obtenir("raspberry_pi.home_net", home_net)
        eve_log_path = config.obtenir("suricata.log_path", eve_log_path)
        interface = config.obtenir("raspberry_pi.network_interface", interface)

    payload = build_suricata_config(interface, eve_log_path, home_net)

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


__all__ = ["build_suricata_config", "generer_config_suricata"]
