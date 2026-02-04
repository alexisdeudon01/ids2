"""
Client minimal AWS OpenSearch.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import boto3
from botocore.exceptions import UnknownServiceError

from ..app.decorateurs import log_appel, metriques, retry
from .opensearch_client import OpenSearchClient

if TYPE_CHECKING:
    from ..interfaces import GestionnaireConfig

logger = logging.getLogger(__name__)


class AWSOpenSearchManager:
    """Gestionnaire AWS pour OpenSearch (connectivite et domaine)."""

    def __init__(self, config: GestionnaireConfig | None = None) -> None:
        self._config = config
        self._endpoint: str | None = None
        self._region: str | None = None
        self._domain_name: str | None = None
        self._client: OpenSearchClient | None = None
        if config:
            self._endpoint = config.obtenir("aws.opensearch_endpoint")
            if not self._endpoint:
                self._endpoint = config.obtenir("aws.opensearch.endpoint")
            self._region = config.obtenir("aws.region")
            self._domain_name = (
                config.obtenir("aws.domain_name")
                or config.obtenir("aws.opensearch.domain_name")
                or config.obtenir("aws.opensearch_domain")
            )
            self._client = OpenSearchClient(config)

    def _build_session(self) -> boto3.Session:
        if not self._config:
            return boto3.Session(region_name=self._region)

        use_instance_profile = bool(self._config.obtenir("aws.credentials.use_instance_profile"))
        access_key = self._config.obtenir("aws.access_key_id")
        secret_key = self._config.obtenir("aws.secret_access_key")
        session_token = self._config.obtenir("aws.session_token")

        if not use_instance_profile and access_key and secret_key:
            return boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                aws_session_token=session_token,
                region_name=self._region,
            )

        return boto3.Session(region_name=self._region)

    def _build_domain_payload(self, domain_name: str) -> dict[str, Any]:
        payload: dict[str, Any] = {"DomainName": domain_name}
        if not self._config:
            return payload

        domain_config = self._config.obtenir("aws.opensearch.domain", {}) or {}
        engine_version = domain_config.get("engine_version") or self._config.obtenir(
            "aws.opensearch.engine_version"
        )
        if engine_version:
            payload["EngineVersion"] = engine_version

        cluster_config = domain_config.get("cluster_config")
        if cluster_config is not None:
            payload["ClusterConfig"] = cluster_config

        ebs_options = domain_config.get("ebs_options")
        if ebs_options is not None:
            payload["EBSOptions"] = ebs_options

        access_policies = domain_config.get("access_policies")
        if access_policies is not None:
            payload["AccessPolicies"] = access_policies

        domain_endpoint_options = domain_config.get("domain_endpoint_options")
        if domain_endpoint_options is not None:
            payload["DomainEndpointOptions"] = domain_endpoint_options

        node_to_node = domain_config.get("node_to_node_encryption")
        if node_to_node is not None:
            payload["NodeToNodeEncryptionOptions"] = node_to_node

        encryption_at_rest = domain_config.get("encryption_at_rest")
        if encryption_at_rest is not None:
            payload["EncryptionAtRestOptions"] = encryption_at_rest

        advanced_security = domain_config.get("advanced_security_options")
        if advanced_security is not None:
            payload["AdvancedSecurityOptions"] = advanced_security

        return payload

    def _build_boto_client(self):
        session = self._build_session()
        try:
            return session.client("opensearch")
        except UnknownServiceError:
            return session.client("es")

    def obtenir_client(self) -> OpenSearchClient | None:
        return self._client

    @log_appel()
    @metriques("aws.opensearch.ping")
    @retry(nb_tentatives=2, delai_initial=1.0, backoff=2.0)
    async def verifier_connexion(self, timeout: float = 5.0) -> bool:
        if not self._endpoint:
            logger.warning("Endpoint OpenSearch non configure")
            return False
        if not self._client:
            logger.warning("Client OpenSearch non initialise")
            return False

        def _call() -> bool:
            return self._client.ping(timeout=timeout)

        return await asyncio.to_thread(_call)

    @log_appel()
    @metriques("aws.opensearch.create_domain")
    @retry(nb_tentatives=2, delai_initial=1.0, backoff=2.0)
    def creer_domaine(self, domain_name: str | None = None) -> dict[str, Any]:
        domaine = domain_name or self._domain_name
        if not domaine:
            raise ValueError("Nom de domaine OpenSearch non configure")
        client = self._build_boto_client()
        payload = self._build_domain_payload(domaine)
        return client.create_domain(**payload)


__all__ = ["AWSOpenSearchManager"]
