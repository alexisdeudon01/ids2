"""
Package Suricata - logique metier IDS.
"""

from .config import build_suricata_config
from .manager import SuricataManager
from .parser import parse_eve_json_line

__all__ = [
    "SuricataManager",
    "build_suricata_config",
    "parse_eve_json_line",
]
