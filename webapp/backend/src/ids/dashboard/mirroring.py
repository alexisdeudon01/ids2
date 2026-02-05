"""
Port mirroring verification via TP-Link web interface.
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx

from ids.domain import MirrorStatus

logger = logging.getLogger(__name__)


class MirrorMonitor:
    """Verify TP-Link TL-SG108E mirroring configuration via HTTP."""

    def __init__(
        self,
        base_url: str | None,
        username: str | None = None,
        password: str | None = None,
        source_port: str = "1",
        mirror_port: str = "5",
    ) -> None:
        self.base_url = base_url
        self.username = username
        self.password = password
        self.source_port = source_port
        self.mirror_port = mirror_port

    async def check_mirroring(self) -> MirrorStatus:
        """Check the switch web UI for active port mirroring."""
        if not self.base_url:
            return MirrorStatus(
                configured=False,
                active=False,
                source_port=self.source_port,
                mirror_port=self.mirror_port,
                message="TP_LINK_SWITCH_URL not configured",
            )

        auth = None
        if self.username and self.password:
            auth = (self.username, self.password)

        try:
            async with httpx.AsyncClient(timeout=10.0, auth=auth, follow_redirects=True) as client:
                response = await client.get(self.base_url)
            content = response.text.lower()
            required_tokens = [
                "mirror",
                self.source_port.lower(),
                self.mirror_port.lower(),
            ]
            is_active = all(token in content for token in required_tokens)
            message = "Mirror configuration detected" if is_active else "Mirror configuration not detected"

            return MirrorStatus(
                configured=True,
                active=is_active,
                source_port=self.source_port,
                mirror_port=self.mirror_port,
                message=message,
                status_code=response.status_code,
                checked_at=datetime.now(),
            )
        except httpx.HTTPError as exc:
            logger.error(f"Mirroring check failed: {exc}")
            return MirrorStatus(
                configured=True,
                active=False,
                source_port=self.source_port,
                mirror_port=self.mirror_port,
                message=f"HTTP error: {exc}",
                checked_at=datetime.now(),
            )
