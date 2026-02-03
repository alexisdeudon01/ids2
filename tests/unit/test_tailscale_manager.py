"""Unit tests for TailscaleManager."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from ids.composants.tailscale_manager import (
    TailscaleManager,
    DeploymentCapabilities,
    deployment_strategy,
    handles_node_type,
)
from ids.domain.tailscale import (
    DeploymentMode,
    DeploymentResult,
    NodeStatus,
    NodeType,
    TailnetConfig,
    TailscaleAuthKey,
    TailscaleDeploymentConfig,
    TailscaleNode,
)


def _utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class TestTailscaleNode:
    """Tests for TailscaleNode dataclass."""

    def test_node_creation(self):
        node = TailscaleNode(
            hostname="test-pi",
            node_id="node123",
            ip_addresses=["192.168.1.10"],
            tailnet_ip="100.64.0.1",
        )
        assert node.hostname == "test-pi"
        assert node.node_id == "node123"
        assert node.status == NodeStatus.PENDING
        assert not node.authorized

    def test_node_is_online(self):
        node = TailscaleNode(hostname="test", status=NodeStatus.ONLINE)
        assert node.is_online()

        node_offline = TailscaleNode(hostname="test", status=NodeStatus.OFFLINE)
        assert not node_offline.is_online()

    def test_node_is_authorized(self):
        node = TailscaleNode(
            hostname="test",
            authorized=True,
            status=NodeStatus.ONLINE,
        )
        assert node.is_authorized()

        node_unauth = TailscaleNode(
            hostname="test",
            authorized=True,
            status=NodeStatus.UNAUTHORIZED,
        )
        assert not node_unauth.is_authorized()


class TestTailscaleAuthKey:
    """Tests for TailscaleAuthKey dataclass."""

    def test_key_creation(self):
        key = TailscaleAuthKey(
            key="tskey-auth-xxx",
            key_id="key123",
            created_at=_utcnow(),
            expires_at=_utcnow() + timedelta(hours=24),
            reusable=True,
            ephemeral=False,
            preauthorized=True,
        )
        assert key.key == "tskey-auth-xxx"
        assert key.reusable
        assert not key.is_expired()

    def test_key_expired(self):
        key = TailscaleAuthKey(
            key="tskey-auth-xxx",
            key_id="key123",
            created_at=_utcnow() - timedelta(hours=48),
            expires_at=_utcnow() - timedelta(hours=24),
        )
        assert key.is_expired()


class TestTailscaleDeploymentConfig:
    """Tests for TailscaleDeploymentConfig dataclass."""

    def test_to_tailscale_up_args_basic(self):
        config = TailscaleDeploymentConfig(
            mode=DeploymentMode.LINUX_SERVICE,
            auth_key="tskey-auth-xxx",
            hostname="test-pi",
        )
        args = config.to_tailscale_up_args()
        assert "--authkey=tskey-auth-xxx" in args
        assert "--hostname=test-pi" in args

    def test_to_tailscale_up_args_full(self):
        config = TailscaleDeploymentConfig(
            mode=DeploymentMode.LINUX_SERVICE,
            auth_key="tskey-auth-xxx",
            hostname="test-pi",
            advertise_exit_node=True,
            advertise_routes=["192.168.1.0/24", "10.0.0.0/8"],
            accept_routes=True,
            accept_dns=True,
            tags=["ci", "ids2"],
        )
        args = config.to_tailscale_up_args()
        assert "--authkey=tskey-auth-xxx" in args
        assert "--hostname=test-pi" in args
        assert "--advertise-exit-node" in args
        assert "--advertise-routes=192.168.1.0/24,10.0.0.0/8" in args
        assert "--accept-routes" in args
        assert "--accept-dns" in args
        assert "--advertise-tags=ci,ids2" in args


class TestDeploymentCapabilities:
    """Tests for DeploymentCapabilities dataclass."""

    def test_default_capabilities(self):
        caps = DeploymentCapabilities()
        assert not caps.has_systemd
        assert not caps.has_docker
        assert not caps.has_docker_compose
        assert not caps.is_in_container
        assert not caps.tailscale_installed
        assert not caps.tailscale_running


class TestDecorators:
    """Tests for custom decorators."""

    def test_deployment_strategy_decorator(self):
        @deployment_strategy(DeploymentMode.LINUX_SERVICE)
        def my_strategy():
            pass

        assert hasattr(my_strategy, "_deployment_mode")
        assert my_strategy._deployment_mode == DeploymentMode.LINUX_SERVICE

    def test_handles_node_type_decorator(self):
        @handles_node_type(NodeType.DEVICE, NodeType.THIRD_PARTY)
        def my_handler():
            pass

        assert hasattr(my_handler, "_handled_node_types")
        assert NodeType.DEVICE in my_handler._handled_node_types
        assert NodeType.THIRD_PARTY in my_handler._handled_node_types


class TestTailscaleManager:
    """Tests for TailscaleManager class."""

    def test_manager_creation_no_config(self):
        manager = TailscaleManager(config=None)
        assert manager.nom_composant == "tailscale"
        assert manager._tailnet_config is None

    def test_select_deployment_mode_systemd(self):
        manager = TailscaleManager(config=None)
        caps = DeploymentCapabilities(
            has_systemd=True,
            has_docker=True,
            is_in_container=False,
        )
        mode = manager.select_best_deployment_mode(caps)
        assert mode == DeploymentMode.LINUX_SERVICE

    def test_select_deployment_mode_docker(self):
        manager = TailscaleManager(config=None)
        caps = DeploymentCapabilities(
            has_systemd=False,
            has_docker=True,
            has_docker_compose=False,
            is_in_container=False,
        )
        mode = manager.select_best_deployment_mode(caps)
        assert mode == DeploymentMode.DOCKER

    def test_select_deployment_mode_docker_compose(self):
        manager = TailscaleManager(config=None)
        caps = DeploymentCapabilities(
            has_systemd=False,
            has_docker=True,
            has_docker_compose=True,
            is_in_container=False,
        )
        mode = manager.select_best_deployment_mode(caps)
        assert mode == DeploymentMode.DOCKER_COMPOSE

    def test_select_deployment_mode_container(self):
        manager = TailscaleManager(config=None)
        caps = DeploymentCapabilities(
            has_systemd=True,
            has_docker=True,
            is_in_container=True,
        )
        mode = manager.select_best_deployment_mode(caps)
        assert mode == DeploymentMode.SIDECAR

    def test_generate_systemd_service(self):
        manager = TailscaleManager(config=None)
        service = manager.generate_systemd_service()
        assert "[Unit]" in service
        assert "[Service]" in service
        assert "[Install]" in service
        assert "tailscaled" in service

    def test_generate_compose_snippet(self):
        manager = TailscaleManager(config=None)
        snippet = manager.generate_compose_snippet(
            hostname="test-pi",
            auth_key="tskey-auth-xxx",
            extra_args="--accept-routes",
        )
        assert "tailscale:" in snippet
        assert "test-pi" in snippet
        assert "tskey-auth-xxx" in snippet

    def test_generate_dockerfile(self):
        manager = TailscaleManager(config=None)
        dockerfile = manager.generate_dockerfile(
            auth_key="tskey-auth-xxx",
            extra_args="--accept-routes",
        )
        assert "FROM tailscale/tailscale" in dockerfile
        assert "tskey-auth-xxx" in dockerfile


class TestTailscaleManagerAsync:
    """Async tests for TailscaleManager."""

    @pytest.mark.asyncio
    async def test_detect_capabilities_local(self):
        manager = TailscaleManager(config=None)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
            caps = await manager.detect_capabilities()
            assert isinstance(caps, DeploymentCapabilities)

    @pytest.mark.asyncio
    async def test_verifier_sante(self):
        manager = TailscaleManager(config=None)
        with patch.object(manager, "detect_capabilities", new_callable=AsyncMock) as mock_detect:
            mock_detect.return_value = DeploymentCapabilities(
                tailscale_installed=True,
                tailscale_running=True,
            )
            health = await manager.verifier_sante()
            assert health.nom_composant == "tailscale"
            assert health.sain is True

    @pytest.mark.asyncio
    async def test_list_nodes_no_config(self):
        manager = TailscaleManager(config=None)
        nodes = await manager.list_nodes()
        assert isinstance(nodes, list)
        assert len(nodes) == 0


class TestDeploymentResult:
    """Tests for DeploymentResult dataclass."""

    def test_success_result(self):
        node = TailscaleNode(hostname="test-pi")
        result = DeploymentResult(
            success=True,
            node=node,
            mode=DeploymentMode.LINUX_SERVICE,
            message="Success",
        )
        assert result.success
        assert result.node.hostname == "test-pi"
        assert result.mode == DeploymentMode.LINUX_SERVICE

    def test_failure_result(self):
        result = DeploymentResult(
            success=False,
            mode=DeploymentMode.DOCKER,
            message="Failed",
            error="Connection refused",
        )
        assert not result.success
        assert result.error == "Connection refused"
