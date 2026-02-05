"""Provisionnement d'un domaine OpenSearch via boto3."""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

try:
    import boto3
    from botocore.exceptions import ClientError, UnknownServiceError
except ImportError as e:  # pragma: no cover - optional dependency
    boto3 = None
    ClientError = Exception
    UnknownServiceError = Exception
    if __name__ == "__main__":
        print(f"⚠️  Warning: Could not import boto3/botocore: {e}")

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover - optional dependency
    tqdm = None

from ..config import ConfigManager

logger = logging.getLogger(__name__)

DEFAULT_ENGINE_VERSION = "OpenSearch_2.11"
DEFAULT_CLUSTER_CONFIG = {
    "InstanceType": "t3.small.search",
    "InstanceCount": 1,
}
DEFAULT_EBS_OPTIONS = {
    "EBSEnabled": True,
    "VolumeType": "gp3",
    "VolumeSize": 10,
}
DEFAULT_ENDPOINT_OPTIONS = {
    "EnforceHTTPS": True,
    "TLSSecurityPolicy": "Policy-Min-TLS-1-2-2019-07",
}
DEFAULT_NODE_TO_NODE = {"Enabled": True}
DEFAULT_ENCRYPTION_AT_REST = {"Enabled": True}


def _build_session(config: ConfigManager) -> boto3.Session:
    if boto3 is None:
        raise ImportError("boto3 is required for OpenSearch domain operations")
    
    use_instance_profile = bool(config.obtenir("aws.credentials.use_instance_profile"))
    access_key = config.obtenir("aws.access_key_id")
    secret_key = config.obtenir("aws.secret_access_key")
    session_token = config.obtenir("aws.session_token")
    region = config.obtenir("aws.region")

    if not use_instance_profile and access_key and secret_key:
        return boto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            aws_session_token=session_token,
            region_name=region,
        )

    return boto3.Session(region_name=region)


def _build_client(session: boto3.Session):
    try:
        return session.client("opensearch")
    except UnknownServiceError:
        return session.client("es")


def _get_account_id(session: boto3.Session) -> str | None:
    try:
        sts = session.client("sts")
        return sts.get_caller_identity().get("Account")
    except Exception as exc:
        logger.warning("Unable to resolve AWS account id: %s", exc)
        return None


def _merge_domain_defaults(domain_config: dict[str, Any]) -> dict[str, Any]:
    merged = dict(domain_config or {})
    merged.setdefault("engine_version", DEFAULT_ENGINE_VERSION)
    merged.setdefault("cluster_config", DEFAULT_CLUSTER_CONFIG)
    merged.setdefault("ebs_options", DEFAULT_EBS_OPTIONS)
    merged.setdefault("domain_endpoint_options", DEFAULT_ENDPOINT_OPTIONS)
    merged.setdefault("node_to_node_encryption", DEFAULT_NODE_TO_NODE)
    merged.setdefault("encryption_at_rest", DEFAULT_ENCRYPTION_AT_REST)
    return merged


def _build_access_policy(region: str, account_id: str, domain_name: str) -> dict[str, Any]:
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": f"arn:aws:iam::{account_id}:root"},
                "Action": "es:*",
                "Resource": f"arn:aws:es:{region}:{account_id}:domain/{domain_name}/*",
            }
        ],
    }


def _build_payload(domain_name: str, domain_config: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {"DomainName": domain_name}
    engine_version = domain_config.get("engine_version")
    if engine_version:
        payload["EngineVersion"] = engine_version

    cluster_config = domain_config.get("cluster_config")
    if cluster_config:
        payload["ClusterConfig"] = cluster_config

    ebs_options = domain_config.get("ebs_options")
    if ebs_options:
        payload["EBSOptions"] = ebs_options

    access_policies = domain_config.get("access_policies")
    if access_policies:
        if isinstance(access_policies, dict):
            access_policies = json.dumps(access_policies)
        payload["AccessPolicies"] = access_policies

    endpoint_options = domain_config.get("domain_endpoint_options")
    if endpoint_options:
        payload["DomainEndpointOptions"] = endpoint_options

    node_to_node = domain_config.get("node_to_node_encryption")
    if node_to_node:
        payload["NodeToNodeEncryptionOptions"] = node_to_node

    encryption_at_rest = domain_config.get("encryption_at_rest")
    if encryption_at_rest:
        payload["EncryptionAtRestOptions"] = encryption_at_rest

    advanced_security = domain_config.get("advanced_security_options")
    if advanced_security:
        payload["AdvancedSecurityOptions"] = advanced_security

    return payload


def _describe_domain(client, domain_name: str) -> dict[str, Any] | None:
    try:
        response = client.describe_domain(DomainName=domain_name)
        return response.get("DomainStatus")
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"ResourceNotFoundException", "ValidationException"}:
            return None
        raise


def _resolve_endpoint(status: dict[str, Any]) -> str | None:
    if not status:
        return None
    if status.get("Endpoint"):
        return status.get("Endpoint")
    endpoints = status.get("Endpoints")
    if isinstance(endpoints, dict):
        return endpoints.get("vpc") or endpoints.get("public")
    return None


def _wait_for_endpoint(client, domain_name: str, timeout: int, poll: int) -> str | None:
    deadline = time.monotonic() + timeout
    start = time.monotonic()
    last = start
    progress = _progress_bar(timeout)
    endpoint: str | None = None
    try:
        while True:
            current_time = time.monotonic()
            if current_time >= deadline:
                break
            status = _describe_domain(client, domain_name)
            endpoint = _resolve_endpoint(status or {})
            if endpoint and status and not status.get("Processing", True):
                if progress is not None:
                    progress.set_postfix_str("ready")
                    remaining = max(0.0, timeout - progress.n)
                    if remaining:
                        progress.update(remaining)
                return endpoint
            if progress is None:
                logger.info("Waiting for OpenSearch domain to be ready...")
            now = time.monotonic()
            if progress is not None:
                delta = now - last
                remaining = max(0.0, timeout - progress.n)
                if remaining:
                    progress.update(min(delta, remaining))
                progress.set_postfix_str("waiting")
                last = now
            time.sleep(poll)
        # Timeout reached - return None if no endpoint found
        return None
    finally:
        if progress is not None:
            progress.close()


def _progress_bar(timeout: int):
    if tqdm is None:
        return None
    return tqdm(
        total=timeout,
        unit="s",
        desc="OpenSearch domain",
        dynamic_ncols=True,
        leave=True,
    )


def _update_config_endpoint(config_path: Path, endpoint: str) -> None:
    content = config_path.read_text(encoding="utf-8")
    pattern = re.compile(r"^(\s*opensearch_endpoint:\s*)([^#]*)(.*)$", re.MULTILINE)
    if pattern.search(content):
        content = pattern.sub(r'\1"' + endpoint + r'"\3', content, count=1)
    else:
        lines = content.splitlines()
        for idx, line in enumerate(lines):
            if line.startswith("aws:"):
                lines.insert(idx + 1, f'  opensearch_endpoint: "{endpoint}"')
                break
        content = "\n".join(lines) + "\n"
    config_path.write_text(content, encoding="utf-8")


def creer_domaine(
    config_path: str,
    secret_path: str | None = None,
    domain_name: str | None = None,
    wait: bool = True,
    timeout: int = 1800,
    poll: int = 30,
    apply_endpoint: bool = True,
) -> dict:
    config_file = Path(config_path)
    secret_file = Path(secret_path) if secret_path else config_file.parent / "secret.json"
    config = ConfigManager(config_path, secret_path=str(secret_file))
    session = _build_session(config)
    client = _build_client(session)

    resolved_domain = (
        domain_name
        or config.obtenir("aws.domain_name")
        or config.obtenir("aws.opensearch.domain_name")
        or config.obtenir("aws.opensearch_domain")
    )
    if not resolved_domain:
        raise ValueError("Nom de domaine OpenSearch non configure")

    region = config.obtenir("aws.region")
    if not region:
        raise ValueError("Region AWS non configuree")

    domain_config = config.obtenir("aws.opensearch.domain", {}) or {}
    domain_config = _merge_domain_defaults(domain_config)

    if not domain_config.get("access_policies"):
        account_id = _get_account_id(session)
        if account_id:
            domain_config["access_policies"] = _build_access_policy(region, account_id, resolved_domain)

    payload = _build_payload(resolved_domain, domain_config)
    existing = _describe_domain(client, resolved_domain)
    response: dict[str, Any]
    if existing:
        logger.info("OpenSearch domain already exists: %s", resolved_domain)
        response = {"DomainStatus": existing}
    else:
        response = client.create_domain(**payload)

    endpoint = _resolve_endpoint(response.get("DomainStatus", {}))
    if wait and not endpoint:
        endpoint = _wait_for_endpoint(client, resolved_domain, timeout, poll)

    if endpoint:
        logger.info("OpenSearch endpoint: %s", endpoint)
        if apply_endpoint:
            _update_config_endpoint(config_file, endpoint)
    else:
        logger.warning("OpenSearch endpoint not available yet.")
    return response


def main() -> None:
    parser = argparse.ArgumentParser(description="Creer un domaine AWS OpenSearch")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Chemin vers config.yaml (defaut: config.yaml)",
    )
    parser.add_argument(
        "--domain-name",
        default=None,
        help="Nom de domaine a creer (override config)",
    )
    parser.add_argument(
        "--secret",
        default=None,
        help="Chemin vers secret.json (defaut: config.yaml dir)",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Ne pas attendre la creation complete du domaine",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=1800,
        help="Timeout d'attente (secondes)",
    )
    parser.add_argument(
        "--poll",
        type=int,
        default=30,
        help="Intervalle de polling (secondes)",
    )
    parser.add_argument(
        "--no-apply-endpoint",
        action="store_true",
        help="Ne pas ecrire l'endpoint dans config.yaml",
    )
    parser.add_argument("--verbose", action="store_true", help="Logs verbeux")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s - %(levelname)s - %(message)s")
    response = creer_domaine(
        args.config,
        secret_path=args.secret,
        domain_name=args.domain_name,
        wait=not args.no_wait,
        timeout=args.timeout,
        poll=args.poll,
        apply_endpoint=not args.no_apply_endpoint,
    )
    print(json.dumps(response, indent=2, default=str))


if __name__ == "__main__":
    main()
