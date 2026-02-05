"""Tests for Raspberry Pi deployment helper."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from ids.deploy import pi_uploader


@pytest.mark.unit
def test_load_deploy_config_uses_pi_ip(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("raspberry_pi:\n  pi_ip: 10.0.0.1\n", encoding="utf-8")

    deploy_config = pi_uploader.load_deploy_config(config_path)

    assert deploy_config.pi_host == "10.0.0.1"
    assert deploy_config.repo_root == tmp_path


@pytest.mark.unit
def test_render_env_file_writes_expected_vars(tmp_path: Path) -> None:
    (tmp_path / "docker").mkdir(parents=True)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "aws:\n  region: eu-central-1\n  opensearch_endpoint: https://example\n",
        encoding="utf-8",
    )
    secret_path = tmp_path / "secret.json"
    secret_path.write_text(
        json.dumps(
            {
                "aws": {
                    "access_key_id": "AKIA_TEST",
                    "secret_access_key": "SECRET_TEST",
                }
            }
        ),
        encoding="utf-8",
    )

    config = pi_uploader.DeployConfig(repo_root=tmp_path, pi_host="pi.local")
    env_path = pi_uploader.render_env_file(config)

    assert env_path is not None
    content = env_path.read_text(encoding="utf-8")
    assert "AWS_ACCESS_KEY_ID=AKIA_TEST" in content
    assert "AWS_SECRET_ACCESS_KEY=SECRET_TEST" in content
    assert "AWS_REGION=eu-central-1" in content
    assert "OPENSEARCH_ENDPOINT=https://example" in content


@pytest.mark.unit
def test_deploy_to_pi_invokes_core_commands(tmp_path: Path) -> None:
    (tmp_path / "docker").mkdir(parents=True)
    (tmp_path / "config.yaml").write_text("raspberry_pi:\n  pi_ip: 10.0.0.1\n", encoding="utf-8")

    calls = []

    def runner(args, check=True, text=True, capture_output=False):
        calls.append(args)
        stdout = "200" if capture_output else ""
        return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")

    config = pi_uploader.DeployConfig(
        repo_root=tmp_path,
        pi_host="10.0.0.1",
        sync_paths=[],
        run_install=False,
    )

    tar_path = pi_uploader.deploy_to_pi(config, runner)

    assert tar_path.name.endswith("ids2-agent_latest.tar")
    assert any(cmd[:2] == ["docker", "build"] for cmd in calls)
    assert any(cmd[:2] == ["docker", "save"] for cmd in calls)
    assert any(cmd[0] == "ssh" for cmd in calls)
