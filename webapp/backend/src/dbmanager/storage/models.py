"""
SQLAlchemy models for IDS dashboard configuration and telemetry.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped

from .database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Secrets(Base, TimestampMixin):
    __tablename__ = "secrets"

    id: Mapped[int] = Column(Integer, primary_key=True)
    aws_access_key_id: Mapped[str | None] = Column(Text, nullable=True)
    aws_secret_access_key: Mapped[str | None] = Column(Text, nullable=True)
    aws_session_token: Mapped[str | None] = Column(Text, nullable=True)
    tailscale_api_key: Mapped[str | None] = Column(Text, nullable=True)
    tailscale_oauth_client_id: Mapped[str | None] = Column(Text, nullable=True)
    tailscale_oauth_client_secret: Mapped[str | None] = Column(Text, nullable=True)
    elasticsearch_username: Mapped[str | None] = Column(Text, nullable=True)
    elasticsearch_password: Mapped[str | None] = Column(Text, nullable=True)
    pi_ssh_user: Mapped[str | None] = Column(Text, nullable=True)
    pi_ssh_password: Mapped[str | None] = Column(Text, nullable=True)
    pi_sudo_password: Mapped[str | None] = Column(Text, nullable=True)


class AwsConfig(Base, TimestampMixin):
    __tablename__ = "aws_config"

    id: Mapped[int] = Column(Integer, primary_key=True)
    region: Mapped[str] = Column(String, default="eu-central-1")
    domain_name: Mapped[str] = Column(String, default="suricata-prod")
    opensearch_endpoint: Mapped[str | None] = Column(String, nullable=True)


class RaspberryPiConfig(Base, TimestampMixin):
    __tablename__ = "raspberry_pi_config"

    id: Mapped[int] = Column(Integer, primary_key=True)
    pi_ip: Mapped[str | None] = Column(String, nullable=True)
    home_net: Mapped[str] = Column(String, default="192.168.178.0/24")
    network_interface: Mapped[str] = Column(String, default="eth0")
    cpu_limit_percent: Mapped[float] = Column(Float, default=70.0)
    ram_limit_percent: Mapped[float] = Column(Float, default=70.0)
    swap_size_gb: Mapped[int] = Column(Integer, default=2)
    cpu_limit_medium_percent: Mapped[float] = Column(Float, default=75.0)
    ram_limit_medium_percent: Mapped[float] = Column(Float, default=75.0)
    cpu_limit_high_percent: Mapped[float] = Column(Float, default=80.0)
    ram_limit_high_percent: Mapped[float] = Column(Float, default=80.0)


class SuricataConfig(Base, TimestampMixin):
    __tablename__ = "suricata_config"

    id: Mapped[int] = Column(Integer, primary_key=True)
    log_path: Mapped[str] = Column(String, default="/mnt/ram_logs/eve.json")
    config_path: Mapped[str] = Column(String, default="webapp/db/config/suricata.yaml")
    rules_path: Mapped[str] = Column(String, default="suricata/rules")
    eve_log_payload: Mapped[bool] = Column(Boolean, default=False)
    eve_log_packet: Mapped[bool] = Column(Boolean, default=False)
    eve_log_http: Mapped[bool] = Column(Boolean, default=True)
    eve_log_dns: Mapped[bool] = Column(Boolean, default=True)
    eve_log_tls: Mapped[bool] = Column(Boolean, default=True)
    eve_log_flow: Mapped[bool] = Column(Boolean, default=True)
    eve_log_stats: Mapped[bool] = Column(Boolean, default=True)
    default_log_dir: Mapped[str] = Column(String, default="/mnt/ram_logs")
    home_net: Mapped[str] = Column(String, default="any")
    external_net: Mapped[str] = Column(String, default="any")
    http_ports: Mapped[str] = Column(String, default="80")
    ssh_ports: Mapped[str] = Column(String, default="22")
    smtp_ports: Mapped[str] = Column(String, default="25")
    dns_ports: Mapped[str] = Column(String, default="53")
    tls_ports: Mapped[str] = Column(String, default="443")


class VectorConfig(Base, TimestampMixin):
    __tablename__ = "vector_config"

    id: Mapped[int] = Column(Integer, primary_key=True)
    index_pattern: Mapped[str] = Column(String, default="suricata-ids2-%Y.%m.%d")
    log_read_path: Mapped[str] = Column(String, default="/mnt/ram_logs/eve.json")
    disk_buffer_max_size: Mapped[str] = Column(String, default="100 GiB")
    redis_buffer_max_size: Mapped[str] = Column(String, default="10 GiB")
    opensearch_buffer_max_size: Mapped[str] = Column(String, default="50 GiB")
    batch_max_events: Mapped[int] = Column(Integer, default=500)
    batch_timeout_secs: Mapped[int] = Column(Integer, default=2)
    read_from: Mapped[str] = Column(String, default="beginning")
    fingerprint_bytes: Mapped[int] = Column(Integer, default=1024)
    redis_host: Mapped[str] = Column(String, default="redis")
    redis_port: Mapped[int] = Column(Integer, default=6379)
    redis_key: Mapped[str] = Column(String, default="vector_logs")
    opensearch_compression: Mapped[str] = Column(String, default="gzip")
    opensearch_request_timeout_secs: Mapped[int] = Column(Integer, default=30)


class RedisConfig(Base, TimestampMixin):
    __tablename__ = "redis_config"

    id: Mapped[int] = Column(Integer, primary_key=True)
    host: Mapped[str] = Column(String, default="redis")
    port: Mapped[int] = Column(Integer, default=6379)
    db: Mapped[int] = Column(Integer, default=0)


class PrometheusConfig(Base, TimestampMixin):
    __tablename__ = "prometheus_config"

    id: Mapped[int] = Column(Integer, primary_key=True)
    port: Mapped[int] = Column(Integer, default=9100)
    docker_port: Mapped[int] = Column(Integer, default=9090)
    update_interval: Mapped[int] = Column(Integer, default=5)


class GrafanaConfig(Base, TimestampMixin):
    __tablename__ = "grafana_config"

    id: Mapped[int] = Column(Integer, primary_key=True)
    docker_port: Mapped[int] = Column(Integer, default=3000)


class DockerConfig(Base, TimestampMixin):
    __tablename__ = "docker_config"

    id: Mapped[int] = Column(Integer, primary_key=True)
    compose_file: Mapped[str] = Column(String, default="docker/docker-compose.yml")
    vector_cpu: Mapped[float] = Column(Float, default=1.0)
    vector_ram_mb: Mapped[int] = Column(Integer, default=1024)
    redis_cpu: Mapped[float] = Column(Float, default=0.5)
    redis_ram_mb: Mapped[int] = Column(Integer, default=512)
    prometheus_cpu: Mapped[float] = Column(Float, default=0.2)
    prometheus_ram_mb: Mapped[int] = Column(Integer, default=256)
    grafana_cpu: Mapped[float] = Column(Float, default=0.2)
    grafana_ram_mb: Mapped[int] = Column(Integer, default=256)
    cadvisor_cpu: Mapped[float] = Column(Float, default=0.1)
    cadvisor_ram_mb: Mapped[int] = Column(Integer, default=64)
    node_exporter_cpu: Mapped[float] = Column(Float, default=0.1)
    node_exporter_ram_mb: Mapped[int] = Column(Integer, default=64)
    fastapi_cpu: Mapped[float] = Column(Float, default=0.5)
    fastapi_ram_mb: Mapped[int] = Column(Integer, default=256)


class TailscaleConfig(Base, TimestampMixin):
    __tablename__ = "tailscale_config"

    id: Mapped[int] = Column(Integer, primary_key=True)
    tailnet: Mapped[str | None] = Column(String, nullable=True)
    dns_enabled: Mapped[bool] = Column(Boolean, default=True)
    magic_dns: Mapped[bool] = Column(Boolean, default=True)
    exit_node_enabled: Mapped[bool] = Column(Boolean, default=False)
    subnet_routes: Mapped[list[str]] = Column(JSON, default=list)
    deployment_mode: Mapped[str] = Column(String, default="auto")
    default_tags: Mapped[list[str]] = Column(JSON, default=lambda: ["ci", "ids2"])


class FastapiConfig(Base, TimestampMixin):
    __tablename__ = "fastapi_config"

    id: Mapped[int] = Column(Integer, primary_key=True)
    port: Mapped[int] = Column(Integer, default=8080)
    host: Mapped[str] = Column(String, default="0.0.0.0")
    log_level: Mapped[str] = Column(String, default="INFO")


class ResourceControllerConfig(Base, TimestampMixin):
    __tablename__ = "resource_controller_config"

    id: Mapped[int] = Column(Integer, primary_key=True)
    check_interval: Mapped[int] = Column(Integer, default=1)
    throttling_enabled: Mapped[bool] = Column(Boolean, default=True)


class ConnectivityConfig(Base, TimestampMixin):
    __tablename__ = "connectivity_config"

    id: Mapped[int] = Column(Integer, primary_key=True)
    check_interval: Mapped[int] = Column(Integer, default=10)
    max_retries: Mapped[int] = Column(Integer, default=5)
    initial_backoff: Mapped[float] = Column(Float, default=1.0)


class ServicesStatus(Base, TimestampMixin):
    __tablename__ = "services_status"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'inactive', 'failed', 'unknown')", name="services_status_check"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True)
    service_name: Mapped[str] = Column(String, unique=True)
    status: Mapped[str] = Column(String, default="unknown")
    enabled: Mapped[bool] = Column(Boolean, default=False)
    last_check: Mapped[datetime | None] = Column(DateTime, nullable=True)
    last_error: Mapped[str | None] = Column(Text, nullable=True)


class DeploymentHistory(Base, TimestampMixin):
    __tablename__ = "deployment_history"
    __table_args__ = (
        CheckConstraint(
            "deployment_type IN ('initial', 'update', 'rollback')",
            name="deployment_type_check",
        ),
        CheckConstraint(
            "component IN ('dashboard', 'suricata', 'vector', 'elasticsearch', 'tailscale', 'opensearch', 'all')",
            name="deployment_component_check",
        ),
        CheckConstraint(
            "status IN ('success', 'failed', 'in_progress')",
            name="deployment_status_check",
        ),
    )

    id: Mapped[int] = Column(Integer, primary_key=True)
    deployment_type: Mapped[str] = Column(String, default="initial")
    component: Mapped[str] = Column(String, default="all")
    status: Mapped[str] = Column(String, default="in_progress")
    error_message: Mapped[str | None] = Column(Text, nullable=True)
    error_diagnosis: Mapped[str | None] = Column(Text, nullable=True)
    started_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = Column(DateTime, nullable=True)


class ErrorLogs(Base, TimestampMixin):
    __tablename__ = "error_logs"

    id: Mapped[int] = Column(Integer, primary_key=True)
    component: Mapped[str] = Column(String)
    error_type: Mapped[str] = Column(String)
    error_message: Mapped[str] = Column(Text)
    traceback: Mapped[str | None] = Column(Text, nullable=True)
    diagnosis: Mapped[str | None] = Column(Text, nullable=True)
    resolved: Mapped[bool] = Column(Boolean, default=False)
    resolved_at: Mapped[datetime | None] = Column(DateTime, nullable=True)


class SystemMetrics(Base):
    __tablename__ = "system_metrics"

    id: Mapped[int] = Column(Integer, primary_key=True)
    cpu_percent: Mapped[float] = Column(Float)
    ram_percent: Mapped[float] = Column(Float)
    disk_percent: Mapped[float] = Column(Float)
    temperature: Mapped[float | None] = Column(Float, nullable=True)
    network_rx_bytes: Mapped[int] = Column(Integer)
    network_tx_bytes: Mapped[int] = Column(Integer)
    network_rx_packets: Mapped[int] = Column(Integer)
    network_tx_packets: Mapped[int] = Column(Integer)
    recorded_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)


class Alerts(Base, TimestampMixin):
    __tablename__ = "alerts"

    id: Mapped[int] = Column(Integer, primary_key=True)
    signature_id: Mapped[int] = Column(Integer)
    signature: Mapped[str] = Column(Text)
    severity: Mapped[int] = Column(Integer)
    src_ip: Mapped[str] = Column(String)
    dest_ip: Mapped[str] = Column(String)
    src_port: Mapped[int | None] = Column(Integer, nullable=True)
    dest_port: Mapped[int | None] = Column(Integer, nullable=True)
    protocol: Mapped[str | None] = Column(String, nullable=True)
    timestamp: Mapped[datetime] = Column(DateTime)
    payload: Mapped[str | None] = Column(Text, nullable=True)


class TailscaleNodes(Base, TimestampMixin):
    __tablename__ = "tailscale_nodes"

    id: Mapped[int] = Column(Integer, primary_key=True)
    node_id: Mapped[str] = Column(String, unique=True)
    hostname: Mapped[str] = Column(String)
    ip: Mapped[str] = Column(String)
    status: Mapped[str] = Column(String)
    last_seen: Mapped[datetime | None] = Column(DateTime, nullable=True)
    tags: Mapped[list[str]] = Column(JSON, default=list)
    latency_ms: Mapped[float | None] = Column(Float, nullable=True)


class ElasticsearchIndices(Base, TimestampMixin):
    __tablename__ = "elasticsearch_indices"

    id: Mapped[int] = Column(Integer, primary_key=True)
    index_name: Mapped[str] = Column(String, unique=True)
    size_bytes: Mapped[int] = Column(Integer)
    document_count: Mapped[int] = Column(Integer)
    creation_date: Mapped[datetime]


class ElasticsearchIndexPatterns(Base, TimestampMixin):
    __tablename__ = "elasticsearch_index_patterns"

    id: Mapped[int] = Column(Integer, primary_key=True)
    pattern_name: Mapped[str] = Column(String, unique=True)
    pattern: Mapped[str] = Column(String)
    time_field: Mapped[str] = Column(String, default="@timestamp")


class ElasticsearchDashboards(Base, TimestampMixin):
    __tablename__ = "elasticsearch_dashboards"

    id: Mapped[int] = Column(Integer, primary_key=True)
    dashboard_name: Mapped[str] = Column(String, unique=True)
    dashboard_id: Mapped[str] = Column(String, unique=True)
    description: Mapped[str | None] = Column(Text, nullable=True)
