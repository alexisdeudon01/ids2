"""
Pydantic schemas for dashboard configuration.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SecretsSchema(BaseModel):
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    tailscale_api_key: str | None = None
    tailscale_oauth_client_id: str | None = None
    tailscale_oauth_client_secret: str | None = None
    elasticsearch_username: str | None = None
    elasticsearch_password: str | None = None
    pi_ssh_user: str | None = None
    pi_ssh_password: str | None = None
    pi_sudo_password: str | None = None


class AwsConfigSchema(BaseModel):
    region: str = "eu-central-1"
    domain_name: str = "suricata-prod"
    opensearch_endpoint: str | None = None


class RaspberryPiConfigSchema(BaseModel):
    pi_ip: str | None = None
    home_net: str = "192.168.178.0/24"
    network_interface: str = "eth0"
    cpu_limit_percent: float = 70.0
    ram_limit_percent: float = 70.0
    swap_size_gb: int = 2
    cpu_limit_medium_percent: float = 75.0
    ram_limit_medium_percent: float = 75.0
    cpu_limit_high_percent: float = 80.0
    ram_limit_high_percent: float = 80.0


class SuricataConfigSchema(BaseModel):
    log_path: str = "/mnt/ram_logs/eve.json"
    config_path: str = "suricata/suricata.yaml"
    rules_path: str = "suricata/rules"
    eve_log_payload: bool = False
    eve_log_packet: bool = False
    eve_log_http: bool = True
    eve_log_dns: bool = True
    eve_log_tls: bool = True
    eve_log_flow: bool = True
    eve_log_stats: bool = True
    default_log_dir: str = "/mnt/ram_logs"
    home_net: str = "any"
    external_net: str = "any"
    http_ports: str = "80"
    ssh_ports: str = "22"
    smtp_ports: str = "25"
    dns_ports: str = "53"
    tls_ports: str = "443"


class VectorConfigSchema(BaseModel):
    index_pattern: str = "suricata-ids2-%Y.%m.%d"
    log_read_path: str = "/mnt/ram_logs/eve.json"
    disk_buffer_max_size: str = "100 GiB"
    redis_buffer_max_size: str = "10 GiB"
    opensearch_buffer_max_size: str = "50 GiB"
    batch_max_events: int = 500
    batch_timeout_secs: int = 2
    read_from: str = "beginning"
    fingerprint_bytes: int = 1024
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_key: str = "vector_logs"
    opensearch_compression: str = "gzip"
    opensearch_request_timeout_secs: int = 30


class TailscaleConfigSchema(BaseModel):
    tailnet: str | None = None
    dns_enabled: bool = True
    magic_dns: bool = True
    exit_node_enabled: bool = False
    subnet_routes: list[str] = Field(default_factory=list)
    deployment_mode: str = "auto"
    default_tags: list[str] = Field(default_factory=lambda: ["ci", "ids2"])


class FastapiConfigSchema(BaseModel):
    port: int = 8080
    host: str = "0.0.0.0"
    log_level: str = "INFO"
