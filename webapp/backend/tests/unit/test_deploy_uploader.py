import subprocess
from pathlib import Path

from ids.deploy.pi_uploader import DeployConfig, build_ssh_command, deploy_to_pi, load_deploy_config


class FakeRunner:
    def __init__(self) -> None:
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append(args)
        stdout = ""
        if "curl" in " ".join(args):
            stdout = "403"
        return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")


def _touch(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_build_ssh_command_includes_port_and_key(tmp_path: Path) -> None:
    key_path = tmp_path / "id_rsa"
    key_path.write_text("dummy")
    config = DeployConfig(
        repo_root=tmp_path,
        pi_host="192.168.1.10",
        pi_port=2222,
        pi_ssh_key=key_path,
    )
    command = build_ssh_command(config, "echo ok")
    assert command[0] == "ssh"
    assert "-p" in command
    assert "2222" in command
    assert "-i" in command
    assert str(key_path) in command
    assert config.ssh_target in command


def test_load_deploy_config_reads_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "aws:\n"
        "  opensearch_endpoint: https://search.example.com\n"
        "raspberry_pi:\n"
        "  pi_ip: 10.0.0.5\n"
    )
    config = load_deploy_config(config_path)
    assert config.pi_host == "10.0.0.5"
    assert config.opensearch_endpoint == "https://search.example.com"


def test_deploy_to_pi_runs_expected_commands(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _touch(repo_root / "requirements.txt", "requests\n")
    _touch(repo_root / "config.yaml", "aws:\n  opensearch_endpoint: https://example.com\n")
    _touch(repo_root / "pyproject.toml", "[project]\nname='ids'\n")
    _touch(repo_root / "src/ids/__init__.py", "")
    _touch(repo_root / "deploy/install.sh", "#!/bin/bash\n")
    _touch(repo_root / "deploy/enable_agent.sh", "#!/bin/bash\n")
    _touch(repo_root / "docker/docker-compose.yml", "version: '3'\n")
    _touch(repo_root / "vector/vector.toml", "")
    _touch(repo_root / "suricata/suricata.yaml", "")

    config = DeployConfig(
        repo_root=repo_root,
        pi_host="192.168.1.10",
        opensearch_endpoint="https://example.com",
        image_name="ids2-agent",
        image_tag="test",
        run_install=True,
        sync_paths=[Path("requirements.txt"), Path("config.yaml"), Path("src"), Path("deploy")],
    )

    runner = FakeRunner()
    deploy_to_pi(config, runner)

    joined = [" ".join(cmd) for cmd in runner.calls]

    assert any("ssh" in cmd and "echo ok" in cmd for cmd in joined)
    assert any("docker --version" in cmd for cmd in joined)
    assert any("curl -sS" in cmd for cmd in joined)
    assert any("docker build" in cmd for cmd in joined)
    assert any("docker save" in cmd for cmd in joined)
    assert any("scp" in cmd and ".tar" in cmd for cmd in joined)
    assert any("docker load" in cmd for cmd in joined)
    assert any("rsync" in cmd and "requirements.txt" in cmd for cmd in joined)
    assert any("rsync" in cmd and "/src" in cmd for cmd in joined)
    assert any("deploy/install.sh" in cmd for cmd in joined)
    assert any("deploy/enable_agent.sh" in cmd for cmd in joined)
    assert any("docker compose up -d" in cmd for cmd in joined)
    assert any("systemctl start ids2-agent.service" in cmd for cmd in joined)

    build_index = next(i for i, cmd in enumerate(joined) if "docker build" in cmd)
    save_index = next(i for i, cmd in enumerate(joined) if "docker save" in cmd)
    scp_index = next(i for i, cmd in enumerate(joined) if "scp" in cmd)
    load_index = next(i for i, cmd in enumerate(joined) if "docker load" in cmd)
    assert build_index < save_index < scp_index < load_index
