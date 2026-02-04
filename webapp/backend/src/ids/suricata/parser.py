"""
Parseur minimal pour les evenements EVE JSON.
"""

from __future__ import annotations

import json
from datetime import datetime

from ..domain.alerte import AlerteIDS, SeveriteAlerte, TypeAlerte


def parse_eve_json_line(line: str) -> AlerteIDS | None:
    """Parse a single EVE JSON line into an AlerteIDS."""
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return None

    alert = data.get("alert")
    if not alert:
        return None

    severity = _map_severite(alert.get("severity"))
    timestamp = _parse_timestamp(data.get("timestamp"))

    return AlerteIDS(
        timestamp=timestamp,
        severite=severity,
        type_alerte=TypeAlerte.INTRUSION,
        source_ip=data.get("src_ip", ""),
        destination_ip=data.get("dest_ip", ""),
        port=data.get("dest_port", 0) or 0,
        protocole=data.get("proto", "TCP") or "TCP",
        signature=alert.get("signature", ""),
        description=alert.get("category", ""),
        metadata=data,
    )


def parser_ligne_eve(ligne: str) -> AlerteIDS | None:
    """Alias Francais pour le parseur EVE JSON."""
    return parse_eve_json_line(ligne)


def _parse_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.utcnow()


def _map_severite(severity: int | None) -> SeveriteAlerte:
    if severity is None:
        return SeveriteAlerte.MOYENNE
    if severity >= 3:
        return SeveriteAlerte.BASSE
    if severity == 2:
        return SeveriteAlerte.MOYENNE
    if severity == 1:
        return SeveriteAlerte.HAUTE
    return SeveriteAlerte.CRITIQUE


__all__ = ["parse_eve_json_line", "parser_ligne_eve"]
