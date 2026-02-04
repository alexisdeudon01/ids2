"""
Setup and configuration module for IDS Dashboard.

Handles automatic setup of:
- Tailscale tailnet configuration
- OpenSearch/Elasticsearch domain creation
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ids.storage import crud, models

logger = logging.getLogger(__name__)


class TailnetSetup:
    """Setup and configure Tailscale tailnet."""

    def __init__(
        self,
        tailnet: str | None = None,
        api_key: str | None = None,
        session: Session | None = None,
    ) -> None:
        """
        Initialize Tailnet setup.

        Args:
            tailnet: Tailnet name (or from env)
            api_key: Tailscale API key (or from env)
        """
        self._session = session
        if session:
            tailscale_cfg = crud.get_or_create_singleton(session, models.TailscaleConfig)
            secrets = crud.get_or_create_singleton(session, models.Secrets)
            self.tailnet = tailnet or tailscale_cfg.tailnet or os.getenv("TAILSCALE_TAILNET")
            self.api_key = api_key or secrets.tailscale_api_key or os.getenv("TAILSCALE_API_KEY")
        else:
            self.tailnet = tailnet or os.getenv("TAILSCALE_TAILNET")
            self.api_key = api_key or os.getenv("TAILSCALE_API_KEY")

    async def verify_tailnet(self) -> dict[str, Any]:
        """
        Verify tailnet exists and is accessible.

        Returns:
            Dictionary with verification results
        """
        if not self.tailnet or not self.api_key:
            return {
                "configured": False,
                "error": "Tailnet name or API key not configured",
            }

        try:
            from tailscale import Tailscale

            async with Tailscale(tailnet=self.tailnet, api_key=self.api_key) as ts:
                devices = await ts.devices()
                return {
                    "configured": True,
                    "tailnet": self.tailnet,
                    "node_count": len(devices.devices) if devices.devices else 0,
                    "status": "connected",
                }

        except Exception as e:
            logger.error(f"Error verifying tailnet: {e}")
            return {
                "configured": False,
                "error": str(e),
                "tailnet": self.tailnet,
            }

    async def create_auth_key(
        self,
        reusable: bool = True,
        ephemeral: bool = False,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Create a Tailscale auth key for node registration.

        Args:
            reusable: Whether the key can be reused
            ephemeral: Whether nodes using this key are ephemeral
            tags: List of ACL tags to apply

        Returns:
            Dictionary with auth key details
        """
        if not self.tailnet or not self.api_key:
            return {
                "success": False,
                "error": "Tailnet name or API key not configured",
            }

        try:
            import json
            import urllib.request
            from urllib.parse import urlparse

            url = f"https://api.tailscale.com/api/v2/tailnet/{self.tailnet}/keys"
            parsed = urlparse(url)
            if parsed.scheme != "https":
                raise ValueError("Only HTTPS URLs allowed")

            payload: dict[str, Any] = {
                "capabilities": {
                    "devices": {
                        "create": {
                            "reusable": reusable,
                            "ephemeral": ephemeral,
                        }
                    }
                }
            }

            if tags:
                payload["capabilities"]["devices"]["create"]["tags"] = tags

            data = json.dumps(payload).encode("utf-8")
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            # bandit: B310 - URL scheme validated above
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                response = json.loads(resp.read().decode("utf-8"))

            return {
                "success": True,
                "key": response.get("key", ""),
                "id": response.get("id", ""),
            }

        except Exception as e:
            logger.error(f"Error creating auth key: {e}")
            return {
                "success": False,
                "error": str(e),
            }


class OpenSearchSetup:
    """Setup and configure OpenSearch/Elasticsearch domain."""

    def __init__(
        self,
        config_path: str | Path | None = None,
        secret_path: str | Path | None = None,
        session: Session | None = None,
    ) -> None:
        """
        Initialize OpenSearch setup.

        Args:
            config_path: Path to config.yaml
            secret_path: Path to secret.json
        """
        if config_path is None:
            config_path = Path("config.yaml")
        if secret_path is None:
            config_path_obj = Path(config_path)
            secret_path = config_path_obj.parent / "secret.json"

        self.config_path = Path(config_path)
        self.secret_path = Path(secret_path) if secret_path else None
        self._session = session

    def _load_db_settings(self) -> tuple[models.AwsConfig | None, models.Secrets | None]:
        if not self._session:
            return None, None
        aws_cfg = crud.get_or_create_singleton(self._session, models.AwsConfig)
        secrets = crud.get_or_create_singleton(self._session, models.Secrets)
        return aws_cfg, secrets

    async def verify_domain(self, domain_name: str | None = None) -> dict[str, Any]:
        """
        Verify OpenSearch domain exists and is accessible.

        Args:
            domain_name: Domain name to check (or from config)

        Returns:
            Dictionary with verification results
        """
        try:
            from ..config.loader import ConfigManager
            from ..deploy.opensearch_domain import _build_client, _build_session, _describe_domain

            db_cfg, db_secrets = self._load_db_settings()
            if db_cfg and db_secrets:
                config = ConfigManager.from_dict(
                    {
                        "aws": {
                            "region": db_cfg.region,
                            "opensearch_endpoint": db_cfg.opensearch_endpoint,
                            "domain_name": db_cfg.domain_name,
                            "access_key_id": db_secrets.aws_access_key_id,
                            "secret_access_key": db_secrets.aws_secret_access_key,
                            "session_token": db_secrets.aws_session_token,
                        },
                    }
                )
                session = _build_session(config)
                client = _build_client(session)
                domain = domain_name or db_cfg.domain_name
            else:
                config = ConfigManager(
                    str(self.config_path),
                    str(self.secret_path) if self.secret_path else None,
                )
                session = _build_session(config)
                client = _build_client(session)
                domain = domain_name or config.obtenir("aws.domain_name") or config.obtenir("aws.opensearch.domain_name")
            if not domain:
                return {
                    "configured": False,
                    "error": "Domain name not configured",
                }

            domain_info = await asyncio.to_thread(_describe_domain, client, domain)

            if domain_info:
                endpoint = domain_info.get("Endpoint") or (domain_info.get("Endpoints", {}) or {}).get("vpc")
                return {
                    "configured": True,
                    "domain_name": domain,
                    "endpoint": endpoint,
                    "status": domain_info.get("Processing", False) and "creating" or domain_info.get("Created", False) and "active" or "unknown",
                }
            else:
                return {
                    "configured": False,
                    "domain_name": domain,
                    "error": "Domain does not exist",
                }

        except Exception as e:
            logger.error(f"Error verifying OpenSearch domain: {e}")
            return {
                "configured": False,
                "error": str(e),
            }

    async def create_domain(
        self,
        domain_name: str | None = None,
        wait: bool = True,
        timeout: int = 1800,
    ) -> dict[str, Any]:
        """
        Create OpenSearch domain.

        Args:
            domain_name: Domain name (or from config)
            wait: Whether to wait for domain to be ready
            timeout: Timeout in seconds

        Returns:
            Dictionary with creation results
        """
        try:
            from ..deploy.opensearch_domain import creer_domaine

            result = await asyncio.to_thread(
                creer_domaine,
                str(self.config_path),
                str(self.secret_path) if self.secret_path else None,
                domain_name,
                wait,
                timeout,
                30,  # poll interval
                True,  # apply_endpoint
            )

            if isinstance(result, dict):
                status = result.get("DomainStatus", {})
                endpoint = status.get("Endpoint") or (status.get("Endpoints", {}) or {}).get("vpc")
                return {
                    "success": True,
                    "domain_name": status.get("DomainName"),
                    "endpoint": endpoint,
                    "status": status,
                }

            return {
                "success": False,
                "error": "Unexpected response format",
            }

        except Exception as e:
            logger.error(f"Error creating OpenSearch domain: {e}")
            return {
                "success": False,
                "error": str(e),
            }


async def setup_infrastructure(
    tailnet: str | None = None,
    tailscale_api_key: str | None = None,
    opensearch_domain: str | None = None,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    Setup complete infrastructure (Tailnet + OpenSearch).

    Args:
        tailnet: Tailnet name
        tailscale_api_key: Tailscale API key
        opensearch_domain: OpenSearch domain name
        config_path: Path to config.yaml

    Returns:
        Dictionary with setup results
    """
    results: dict[str, Any] = {
        "tailnet": {},
        "opensearch": {},
    }

    # Setup Tailnet
    if tailnet and tailscale_api_key:
        tailnet_setup = TailnetSetup(tailnet, tailscale_api_key)
        results["tailnet"] = await tailnet_setup.verify_tailnet()

    # Setup OpenSearch
    opensearch_setup = OpenSearchSetup(config_path)
    if opensearch_domain:
        # Try to create domain
        results["opensearch"] = await opensearch_setup.create_domain(opensearch_domain)
    else:
        # Just verify existing
        results["opensearch"] = await opensearch_setup.verify_domain()

    return results
