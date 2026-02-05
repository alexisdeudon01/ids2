"""
OpenSearch client helper.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import boto3
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection

from ..app.decorateurs import log_appel, metriques, retry

if TYPE_CHECKING:
    from ..interfaces import GestionnaireConfig

logger = logging.getLogger(__name__)


class OpenSearchClient:
    """OpenSearch client wrapper based on opensearch-py."""

    def __init__(self, config: GestionnaireConfig) -> None:
        self._config = config
        self._client: OpenSearch | None = None

    def _resolve_endpoint(self) -> str | None:
        return self._config.obtenir("aws.opensearch_endpoint") or self._config.obtenir(
            "aws.opensearch.endpoint"
        )

    def _resolve_region(self) -> str | None:
        return self._config.obtenir("aws.region")

    def _build_session(self, region: str | None) -> boto3.Session:
        use_instance_profile = bool(self._config.obtenir("aws.credentials.use_instance_profile"))
        access_key = self._config.obtenir("aws.access_key_id")
        secret_key = self._config.obtenir("aws.secret_access_key")
        session_token = self._config.obtenir("aws.session_token")

        if not use_instance_profile and access_key and secret_key:
            return boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                aws_session_token=session_token,
                region_name=region,
            )

        return boto3.Session(region_name=region)

    def _should_use_sigv4(self, host: str) -> bool:
        configured = self._config.obtenir("aws.opensearch.use_aws_auth")
        if configured is not None:
            return bool(configured)
        return "amazonaws.com" in host

    def _resolve_auth(self, host: str) -> object | None:
        username = self._config.obtenir("aws.opensearch.username")
        password = self._config.obtenir("aws.opensearch.password")
        if username and password:
            return (username, password)

        if not self._should_use_sigv4(host):
            return None

        region = self._resolve_region()
        if not region:
            logger.warning("Region AWS non configuree pour OpenSearch.")
            return None

        session = self._build_session(region)
        credentials = session.get_credentials()
        if not credentials:
            logger.warning("Credentials AWS introuvables pour OpenSearch.")
            return None

        service = "aoss" if ".aoss.amazonaws.com" in host else "es"
        return AWSV4SignerAuth(credentials, region, service)

    def _parse_endpoint(self, endpoint: str) -> tuple[str, int, bool]:
        normalized = endpoint
        if "://" not in normalized:
            normalized = f"https://{normalized}"
        parsed = urlparse(normalized)
        host = parsed.hostname or endpoint
        use_ssl = parsed.scheme == "https"
        port = parsed.port or (443 if use_ssl else 80)
        return host, port, use_ssl

    def _build_client(self) -> OpenSearch | None:
        endpoint = self._resolve_endpoint()
        if not endpoint:
            return None
        host, port, use_ssl = self._parse_endpoint(endpoint)
        http_auth = self._resolve_auth(host)
        verify_certs = self._config.obtenir("aws.opensearch.verify_certs", use_ssl)
        ssl_assert_hostname = self._config.obtenir("aws.opensearch.ssl_assert_hostname", False)
        ca_certs = self._config.obtenir("aws.opensearch.ca_certs")

        client_kwargs = {
            "hosts": [{"host": host, "port": port}],
            "http_compress": True,
            "use_ssl": use_ssl,
            "verify_certs": verify_certs,
            "ssl_assert_hostname": ssl_assert_hostname,
            "ssl_show_warn": False,
        }
        if http_auth:
            client_kwargs["http_auth"] = http_auth
            client_kwargs["connection_class"] = RequestsHttpConnection
        if ca_certs:
            client_kwargs["ca_certs"] = ca_certs

        return OpenSearch(**client_kwargs)

    @property
    def client(self) -> OpenSearch | None:
        if self._client is None:
            self._client = self._build_client()
        return self._client

    @log_appel()
    @metriques("opensearch.ping")
    @retry(nb_tentatives=2, delai_initial=0.5, backoff=2.0)
    def ping(self, timeout: float = 3.0) -> bool:
        """Ping the OpenSearch endpoint if configured."""

        client = self.client
        if not client:
            return False
        try:
            return bool(client.ping(request_timeout=timeout))
        except Exception as exc:
            logger.warning("Ping OpenSearch echoue: %s", exc)
            return False


__all__ = ["OpenSearchClient"]
