"""Tests unitaires pour le deploy helper."""

import subprocess
from unittest.mock import Mock

from ids.app.deploy_helper import DeployConfig, DeployHelper


def test_deploy_flow_invokes_commands(tmp_path, monkeypatch):
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM scratch\n")

    requirements = tmp_path / "requirements.txt"
    requirements.write_text("pyyaml\n")

    config = tmp_path / "config.yaml"
    config.write_text("aws:\n  region: eu-west-1\n")

    secret = tmp_path / "secret.json"
    secret.write_text('{"aws": {"access_key_id": "x", "secret_access_key": "y"}}\n')

    compose_dir = tmp_path / "docker"
    compose_dir.mkdir()
    compose = compose_dir / "docker-compose.yml"
    compose.write_text("services: {}\n")

    runner = Mock()
    runner.run.side_effect = lambda cmd, check=True: subprocess.CompletedProcess(cmd, 0)

    get_mock = Mock(return_value=Mock(status_code=200))
    monkeypatch.setattr("ids.app.deploy_helper.requests.get", get_mock)

    deploy_config = DeployConfig(
        pi_host="pi.local",
        opensearch_endpoint="https://search.example.com",
        dockerfile=str(dockerfile),
        requirements_path=str(requirements),
        config_path=str(config),
        secret_path=str(secret),
        compose_path=str(compose),
    )
    helper = DeployHelper(deploy_config, runner=runner)

    helper.deploy()

    commands = [" ".join(call.args[0]) for call in runner.run.call_args_list]
    assert any("docker info" in cmd for cmd in commands)
    assert any("docker build" in cmd for cmd in commands)
    assert any("docker save" in cmd for cmd in commands)
    assert any(cmd.startswith("scp ") for cmd in commands)
    assert any("docker load" in cmd for cmd in commands)
    assert any("systemctl enable ids2-agent.service" in cmd for cmd in commands)
    get_mock.assert_called_once_with("https://search.example.com", timeout=5)
