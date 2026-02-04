"""
Gestionnaire complet pour AWS OpenSearch.

Utilise boto3 et opensearch-py pour la gestion complète des domaines.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError, UnknownServiceError

logger = logging.getLogger(__name__)

try:
    from opensearchpy import OpenSearch, RequestsHttpConnection
    from requests_aws4auth import AWS4Auth

    OPENSEARCH_AVAILABLE = True
except ImportError:
    OPENSEARCH_AVAILABLE = False
    logger.warning(
        "opensearch-py not available. Install with: pip install opensearch-py requests-aws4auth"
    )


@dataclass
class OpenSearchDomainStatus:
    """Statut d'un domaine OpenSearch."""

    domain_name: str
    domain_id: str
    arn: str
    endpoint: Optional[str]
    processing: bool
    created: bool
    deleted: bool
    engine_version: str
    cluster_config: Dict[str, Any]
    ebs_options: Dict[str, Any]
    access_policies: Optional[str] = None


@dataclass
class OpenSearchIndex:
    """Représente un index OpenSearch."""

    name: str
    health: str  # green, yellow, red
    status: str  # open, close
    doc_count: int
    size_bytes: int
    primary_shards: int
    replica_shards: int


class OpenSearchDomainManager:
    """
    Gestionnaire complet pour les domaines AWS OpenSearch.

    Fonctionnalités:
    - Création/suppression de domaines
    - Monitoring du statut
    - Gestion des index
    - Tests de connectivité
    - Scaling (instances, storage)
    """

    def __init__(
        self,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
        region: str = "us-east-1",
    ):
        """
        Initialise le gestionnaire OpenSearch.

        Args:
            aws_access_key_id: AWS access key
            aws_secret_access_key: AWS secret key
            aws_session_token: AWS session token (optionnel)
            region: Région AWS
        """
        self.region = region

        # Créer session boto3
        if aws_access_key_id and aws_secret_access_key:
            self.session = boto3.Session(
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                aws_session_token=aws_session_token,
                region_name=region,
            )
        else:
            # Utiliser les credentials par défaut (IAM role, env vars, etc.)
            self.session = boto3.Session(region_name=region)

        # Client OpenSearch (ou ES pour anciennes régions)
        try:
            self.client = self.session.client("opensearch")
        except UnknownServiceError:
            self.client = self.session.client("es")

    # =========================================================================
    # Domain Management
    # =========================================================================

    def create_domain(
        self,
        domain_name: str,
        instance_type: str = "t3.small.search",
        instance_count: int = 1,
        volume_size_gb: int = 10,
        engine_version: str = "OpenSearch_2.11",
        wait: bool = True,
        timeout: int = 1800,
    ) -> OpenSearchDomainStatus:
        """
        Crée un nouveau domaine OpenSearch.

        Args:
            domain_name: Nom du domaine
            instance_type: Type d'instance
            instance_count: Nombre d'instances
            volume_size_gb: Taille du volume EBS en GB
            engine_version: Version du moteur
            wait: Attendre que le domaine soit prêt
            timeout: Timeout d'attente en secondes

        Returns:
            Statut du domaine
        """
        logger.info(f"Creating OpenSearch domain: {domain_name}")

        # Vérifier si le domaine existe déjà
        existing = self.get_domain_status(domain_name)
        if existing and not existing.deleted:
            logger.info(f"Domain already exists: {domain_name}")
            return existing

        # Construire la configuration
        payload = {
            "DomainName": domain_name,
            "EngineVersion": engine_version,
            "ClusterConfig": {
                "InstanceType": instance_type,
                "InstanceCount": instance_count,
                "DedicatedMasterEnabled": False,
                "ZoneAwarenessEnabled": False,
            },
            "EBSOptions": {
                "EBSEnabled": True,
                "VolumeType": "gp3",
                "VolumeSize": volume_size_gb,
            },
            "AccessPolicies": self._build_open_access_policy(domain_name),
            "DomainEndpointOptions": {
                "EnforceHTTPS": True,
                "TLSSecurityPolicy": "Policy-Min-TLS-1-2-2019-07",
            },
            "NodeToNodeEncryptionOptions": {"Enabled": True},
            "EncryptionAtRestOptions": {"Enabled": True},
        }

        # Créer le domaine
        response = self.client.create_domain(**payload)
        domain_status = self._parse_domain_status(response["DomainStatus"])

        # Attendre que le domaine soit prêt
        if wait:
            domain_status = self.wait_for_domain_ready(domain_name, timeout=timeout)

        return domain_status

    def get_domain_status(self, domain_name: str) -> Optional[OpenSearchDomainStatus]:
        """
        Récupère le statut d'un domaine.

        Args:
            domain_name: Nom du domaine

        Returns:
            Statut du domaine ou None si non trouvé
        """
        try:
            response = self.client.describe_domain(DomainName=domain_name)
            return self._parse_domain_status(response["DomainStatus"])
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                return None
            raise

    def list_domains(self) -> List[str]:
        """
        Liste tous les domaines OpenSearch du compte.

        Returns:
            Liste des noms de domaines
        """
        response = self.client.list_domain_names()
        return [d["DomainName"] for d in response.get("DomainNames", [])]

    def delete_domain(self, domain_name: str) -> bool:
        """
        Supprime un domaine OpenSearch.

        Args:
            domain_name: Nom du domaine

        Returns:
            True si succès
        """
        try:
            self.client.delete_domain(DomainName=domain_name)
            logger.info(f"Domain deletion initiated: {domain_name}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete domain {domain_name}: {e}")
            return False

    def wait_for_domain_ready(
        self,
        domain_name: str,
        timeout: int = 1800,
        poll_interval: int = 30,
    ) -> OpenSearchDomainStatus:
        """
        Attend qu'un domaine soit prêt.

        Args:
            domain_name: Nom du domaine
            timeout: Timeout en secondes
            poll_interval: Intervalle de polling en secondes

        Returns:
            Statut final du domaine
        """
        logger.info(f"Waiting for domain {domain_name} to be ready (timeout: {timeout}s)...")

        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self.get_domain_status(domain_name)

            if not status:
                raise ValueError(f"Domain {domain_name} not found")

            if status.endpoint and not status.processing:
                logger.info(f"Domain ready: {domain_name} -> {status.endpoint}")
                return status

            logger.info(f"Domain still processing... ({int(time.time() - start_time)}s elapsed)")
            time.sleep(poll_interval)

        raise TimeoutError(f"Domain {domain_name} not ready after {timeout}s")

    # =========================================================================
    # Index Management
    # =========================================================================

    def get_opensearch_client(self, endpoint: str) -> Optional[OpenSearch]:
        """
        Crée un client OpenSearch pour interagir avec les index.

        Args:
            endpoint: Endpoint du domaine (sans https://)

        Returns:
            Client OpenSearch
        """
        if not OPENSEARCH_AVAILABLE:
            logger.error("opensearch-py not available")
            return None

        # Créer AWS4Auth pour l'authentification
        credentials = self.session.get_credentials()
        aws_auth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            self.region,
            "es",
            session_token=credentials.token,
        )

        client = OpenSearch(
            hosts=[{"host": endpoint, "port": 443}],
            http_auth=aws_auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=30,
        )

        return client

    def list_indexes(self, endpoint: str) -> List[OpenSearchIndex]:
        """
        Liste tous les index d'un domaine.

        Args:
            endpoint: Endpoint du domaine

        Returns:
            Liste des index
        """
        client = self.get_opensearch_client(endpoint)
        if not client:
            return []

        try:
            # Récupérer les stats des index
            cat_response = client.cat.indices(format="json")

            indexes = []
            for idx in cat_response:
                indexes.append(
                    OpenSearchIndex(
                        name=idx.get("index", ""),
                        health=idx.get("health", "unknown"),
                        status=idx.get("status", "unknown"),
                        doc_count=int(idx.get("docs.count", 0)),
                        size_bytes=int(idx.get("store.size", 0)),
                        primary_shards=int(idx.get("pri", 1)),
                        replica_shards=int(idx.get("rep", 0)),
                    )
                )

            return indexes

        except Exception as e:
            logger.error(f"Failed to list indexes: {e}")
            return []

    def create_index(
        self,
        endpoint: str,
        index_name: str,
        mappings: Optional[Dict[str, Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Crée un nouvel index.

        Args:
            endpoint: Endpoint du domaine
            index_name: Nom de l'index
            mappings: Mappings de l'index
            settings: Settings de l'index

        Returns:
            True si succès
        """
        client = self.get_opensearch_client(endpoint)
        if not client:
            return False

        body = {}
        if mappings:
            body["mappings"] = mappings
        if settings:
            body["settings"] = settings

        try:
            client.indices.create(index=index_name, body=body)
            logger.info(f"Index created: {index_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create index {index_name}: {e}")
            return False

    def delete_index(self, endpoint: str, index_name: str) -> bool:
        """
        Supprime un index.

        Args:
            endpoint: Endpoint du domaine
            index_name: Nom de l'index

        Returns:
            True si succès
        """
        client = self.get_opensearch_client(endpoint)
        if not client:
            return False

        try:
            client.indices.delete(index=index_name)
            logger.info(f"Index deleted: {index_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete index {index_name}: {e}")
            return False

    # =========================================================================
    # Connectivity Testing
    # =========================================================================

    def ping_domain(self, endpoint: str, timeout: int = 10) -> bool:
        """
        Teste la connectivité à un domaine OpenSearch.

        Args:
            endpoint: Endpoint du domaine
            timeout: Timeout en secondes

        Returns:
            True si accessible
        """
        client = self.get_opensearch_client(endpoint)
        if not client:
            return False

        try:
            info = client.info(request_timeout=timeout)
            logger.info(
                f"OpenSearch ping successful: {info.get('version', {}).get('number', 'unknown')}"
            )
            return True
        except Exception as e:
            logger.error(f"OpenSearch ping failed: {e}")
            return False

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _parse_domain_status(self, status: Dict[str, Any]) -> OpenSearchDomainStatus:
        """Parse le statut d'un domaine depuis la réponse API."""
        return OpenSearchDomainStatus(
            domain_name=status["DomainName"],
            domain_id=status["DomainId"],
            arn=status["ARN"],
            endpoint=status.get("Endpoint"),
            processing=status.get("Processing", False),
            created=status.get("Created", False),
            deleted=status.get("Deleted", False),
            engine_version=status.get("EngineVersion", "unknown"),
            cluster_config=status.get("ClusterConfig", {}),
            ebs_options=status.get("EBSOptions", {}),
            access_policies=status.get("AccessPolicies"),
        )

    def _build_open_access_policy(self, domain_name: str) -> str:
        """
        Construit une policy d'accès ouverte (pour dev/test).

        ATTENTION: À restreindre en production !
        """
        account_id = self._get_account_id()

        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": f"arn:aws:iam::{account_id}:root"},
                    "Action": "es:*",
                    "Resource": f"arn:aws:es:{self.region}:{account_id}:domain/{domain_name}/*",
                }
            ],
        }

        return json.dumps(policy)

    def _get_account_id(self) -> str:
        """Récupère l'AWS Account ID."""
        sts = self.session.client("sts")
        return sts.get_caller_identity()["Account"]


__all__ = [
    "OpenSearchDomainManager",
    "OpenSearchDomainStatus",
    "OpenSearchIndex",
]
