"""Pi upload and install flow for IDS2."""

from __future__ import annotations

import argparse
import inspect
import json
import logging
import shlex
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

Runner = Callable[..., subprocess.CompletedProcess]

DEFAULT_SYNC_PATHS = [
    Path("requirements.txt"),
    Path("pyproject.toml"),
    Path("config.yaml"),
    Path("secret.json"),
    Path("src"),
    Path("deploy"),
    Path("docker"),
    Path("vector"),
    Path("suricata"),
]


@dataclass
class DeployConfig:
    repo_root: Path
    pi_host: str
    pi_user: str = "pi"
    pi_port: int = 22
    pi_ssh_key: Path | None = None
    sudo_password: str | None = None
    remote_dir: Path = Path("/opt/ids2")
    image_name: str = "ids2-agent"
    image_tag: str = "latest"
    dockerfile: Path = Path("Dockerfile")
    opensearch_endpoint: str | None = None
    run_install: bool = True
    include_tests: bool = False
    test_artifacts: list[Path] = field(default_factory=list)
    sync_paths: list[Path] | None = None
    verbose: bool = False

    @property
    def image_ref(self) -> str:
        return f"{self.image_name}:{self.image_tag}"

    @property
    def ssh_target(self) -> str:
        return f"{self.pi_user}@{self.pi_host}"


def load_yaml_config(config_path: Path) -> dict:
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data if isinstance(data, dict) else {}


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle) or {}
    return data if isinstance(data, dict) else {}


def _extract_pi_host(config_data: dict) -> str | None:
    raspberry = config_data.get("raspberry_pi", {}) if isinstance(config_data, dict) else {}
    return raspberry.get("pi_ip") or raspberry.get("host")


def _extract_opensearch_endpoint(config_data: dict) -> str | None:
    aws = config_data.get("aws", {}) if isinstance(config_data, dict) else {}
    endpoint = aws.get("opensearch_endpoint")
    if endpoint:
        return endpoint
    opensearch = aws.get("opensearch", {}) if isinstance(aws, dict) else {}
    return opensearch.get("endpoint")


def load_deploy_config(
    config_path: Path,
    repo_root: Path | None = None,
    pi_host: str | None = None,
    opensearch_endpoint: str | None = None,
    **overrides: object,
) -> DeployConfig:
    config_data = load_yaml_config(config_path)
    resolved_repo_root = repo_root or config_path.parent
    resolved_pi_host = pi_host or _extract_pi_host(config_data)
    resolved_opensearch = opensearch_endpoint or _extract_opensearch_endpoint(config_data)
    if not resolved_pi_host:
        raise ValueError("pi_host is required (missing in config.yaml and not provided).")
    deploy_config = DeployConfig(
        repo_root=resolved_repo_root,
        pi_host=resolved_pi_host,
        opensearch_endpoint=resolved_opensearch,
    )
    for key, value in overrides.items():
        if value is None:
            continue
        if hasattr(deploy_config, key):
            setattr(deploy_config, key, value)
    return deploy_config


def run_command(
    args: Sequence[str],
    runner: Runner = subprocess.run,
    *,
    capture_output: bool = False,
    check: bool = True,
    input_data: str | None = None,
) -> subprocess.CompletedProcess:
    command = [str(arg) for arg in args]
    logger.debug("Running command: %s", " ".join(shlex.quote(part) for part in command))
    kwargs = {"check": check, "text": True, "capture_output": capture_output}
    if input_data is not None and _runner_supports_input(runner):
        kwargs["input"] = input_data
    return runner(command, **kwargs)


def _runner_supports_input(runner: Runner) -> bool:
    try:
        signature = inspect.signature(runner)
    except (TypeError, ValueError):
        return False
    return "input" in signature.parameters


def _base_ssh_options(config: DeployConfig) -> list[str]:
    options = [
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ConnectTimeout=10",
    ]
    if config.pi_ssh_key:
        options.extend(["-i", str(config.pi_ssh_key)])
    return options


def build_ssh_command(config: DeployConfig, remote_command: str) -> list[str]:
    return [
        "ssh",
        "-p",
        str(config.pi_port),
        *_base_ssh_options(config),
        config.ssh_target,
        remote_command,
    ]


def build_scp_command(config: DeployConfig, local_path: Path, remote_path: str) -> list[str]:
    return [
        "scp",
        "-P",
        str(config.pi_port),
        *_base_ssh_options(config),
        str(local_path),
        f"{config.ssh_target}:{remote_path}",
    ]


def build_rsync_command(config: DeployConfig, local_path: Path, remote_path: Path) -> list[str]:
    ssh_parts = ["ssh", "-p", str(config.pi_port), *_base_ssh_options(config)]
    ssh_command = " ".join(shlex.quote(part) for part in ssh_parts)
    local_value = str(local_path)
    remote_value = remote_path.as_posix()
    if local_path.is_dir():
        local_value = f"{local_value}/"
        remote_value = f"{remote_value}/"
    command = [
        "rsync",
        "-az",
    ]
    if config.verbose:
        command.extend(["--info=progress2", "--stats", "--human-readable"])
    command.extend(
        [
            "-e",
            ssh_command,
            local_value,
            f"{config.ssh_target}:{remote_value}",
        ]
    )
    return command


def run_ssh_command(
    config: DeployConfig,
    remote_command: str,
    runner: Runner = subprocess.run,
    *,
    capture_output: bool = False,
    sudo: bool = False,
) -> subprocess.CompletedProcess:
    input_data = None
    if sudo:
        remote_command = f"sh -lc {shlex.quote(remote_command)}"
        if config.sudo_password:
            remote_command = f"sudo -S -p '' {remote_command}"
            input_data = f"{config.sudo_password}\n"
        else:
            remote_command = f"sudo -n {remote_command}"
    return run_command(
        build_ssh_command(config, remote_command),
        runner,
        capture_output=capture_output,
        input_data=input_data,
    )


def check_ssh(config: DeployConfig, runner: Runner = subprocess.run) -> None:
    run_ssh_command(config, "echo ok", runner)


def check_docker(config: DeployConfig, runner: Runner = subprocess.run) -> None:
    run_ssh_command(config, "docker --version", runner)


def check_opensearch(config: DeployConfig, runner: Runner = subprocess.run) -> None:
    if not config.opensearch_endpoint:
        logger.info("No OpenSearch endpoint configured. Skipping connectivity check.")
        return
    endpoint = shlex.quote(config.opensearch_endpoint)
    command = f'curl -sS -o /dev/null -w "%{{http_code}}" {endpoint}'
    result = run_ssh_command(config, command, runner, capture_output=True)
    status = (result.stdout or "").strip()
    if not status.isdigit():
        raise RuntimeError(f"OpenSearch connectivity check failed (no status code): {status}")
    if status == "000" or int(status) >= 500:
        raise RuntimeError(f"OpenSearch connectivity check failed with status {status}.")


def build_image(config: DeployConfig, runner: Runner = subprocess.run) -> None:
    dockerfile = config.dockerfile
    if not dockerfile.is_absolute():
        dockerfile = config.repo_root / dockerfile
    run_command(
        ["docker", "build", "-t", config.image_ref, "-f", str(dockerfile), str(config.repo_root)],
        runner,
    )


def save_image(
    config: DeployConfig, runner: Runner = subprocess.run, output_dir: Path | None = None
) -> Path:
    output_root = output_dir or (config.repo_root / "dist")
    output_root.mkdir(parents=True, exist_ok=True)
    safe_name = config.image_name.replace("/", "_")
    tar_path = output_root / f"{safe_name}_{config.image_tag}.tar"
    run_command(["docker", "save", "-o", str(tar_path), config.image_ref], runner)
    return tar_path


def upload_and_load_image(
    config: DeployConfig, tar_path: Path, runner: Runner = subprocess.run
) -> None:
    # Use system temp directory instead of hardcoded /tmp
    remote_tar = f"{tempfile.gettempdir()}/{tar_path.name}"
    run_command(build_scp_command(config, tar_path, remote_tar), runner)
    run_ssh_command(config, f"docker load -i {shlex.quote(remote_tar)}", runner, sudo=True)
    run_ssh_command(config, f"rm -f {shlex.quote(remote_tar)}", runner)


def ensure_remote_root(config: DeployConfig, runner: Runner = subprocess.run) -> None:
    remote_root = shlex.quote(config.remote_dir.as_posix())
    owner = f"{config.pi_user}:{config.pi_user}"
    command = f"mkdir -p {remote_root} && chown -R {shlex.quote(owner)} {remote_root}"
    run_ssh_command(config, command, runner, sudo=True)


def collect_sync_entries(config: DeployConfig) -> list[tuple[Path, Path]]:
    paths: list[Path] = []
    if config.sync_paths is not None:
        paths = list(config.sync_paths)
    else:
        paths = list(DEFAULT_SYNC_PATHS)
        if config.include_tests:
            paths.append(Path("tests"))
        if config.test_artifacts:
            paths.extend(config.test_artifacts)

    entries: list[tuple[Path, Path]] = []
    for path in paths:
        local_path = path if path.is_absolute() else config.repo_root / path
        if not local_path.exists():
            logger.warning("Skipping missing path: %s", local_path)
            continue
        relative_path = path
        if path.is_absolute():
            try:
                relative_path = path.relative_to(config.repo_root)
            except ValueError:
                relative_path = Path(path.name)
                logger.warning("Path %s is outside repo_root; syncing basename only.", path)
        entries.append((local_path, config.remote_dir / relative_path))
    return entries


def sync_paths(config: DeployConfig, runner: Runner = subprocess.run) -> None:
    for local_path, remote_path in collect_sync_entries(config):
        remote_parent = remote_path if local_path.is_dir() else remote_path.parent
        run_command(
            build_ssh_command(config, f"mkdir -p {shlex.quote(remote_parent.as_posix())}"),
            runner,
        )
        run_command(build_rsync_command(config, local_path, remote_path), runner)


def render_env_file(config: DeployConfig) -> Path | None:
    """Crée un fichier docker/.env à partir de config.yaml et secret.json."""
    config_path = config.repo_root / "config.yaml"
    config_data = load_yaml_config(config_path)
    secret_data = _load_json(config.repo_root / "secret.json")

    aws_config = config_data.get("aws", {}) if isinstance(config_data, dict) else {}
    opensearch = aws_config.get("opensearch", {}) if isinstance(aws_config, dict) else {}
    endpoint = aws_config.get("opensearch_endpoint") or opensearch.get("endpoint")
    region = aws_config.get("region")

    secret_aws = secret_data.get("aws", {}) if isinstance(secret_data, dict) else {}

    env_lines: list[str] = []
    if secret_aws.get("access_key_id"):
        env_lines.append(f"AWS_ACCESS_KEY_ID={secret_aws['access_key_id']}")
    if secret_aws.get("secret_access_key"):
        env_lines.append(f"AWS_SECRET_ACCESS_KEY={secret_aws['secret_access_key']}")
    if region:
        env_lines.append(f"AWS_REGION={region}")
    if endpoint:
        env_lines.append(f"OPENSEARCH_ENDPOINT={endpoint}")

    if not env_lines:
        logger.info("Aucune variable à écrire dans docker/.env")
        return None

    env_path = config.repo_root / "docker" / ".env"
    env_path.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
    logger.info("docker/.env généré (%s variables)", len(env_lines))
    return env_path


def run_install(config: DeployConfig, runner: Runner = subprocess.run) -> None:
    if not config.run_install:
        return
    command = f"cd {shlex.quote(config.remote_dir.as_posix())} && bash deploy/install.sh"
    run_ssh_command(config, command, runner, sudo=True)


def enable_services(config: DeployConfig, runner: Runner = subprocess.run) -> None:
    command = f"cd {shlex.quote(config.remote_dir.as_posix())} && bash deploy/enable_agent.sh"
    run_ssh_command(config, command, runner, sudo=True)


def start_compose_stack(config: DeployConfig, runner: Runner = subprocess.run) -> None:
    compose_dir = config.remote_dir / "docker"
    command = f"cd {shlex.quote(compose_dir.as_posix())} && docker compose up -d"
    run_ssh_command(config, command, runner, sudo=True)


def start_services(config: DeployConfig, runner: Runner = subprocess.run) -> None:
    run_ssh_command(config, "systemctl start suricata.service", runner, sudo=True)
    run_ssh_command(config, "systemctl start ids2-agent.service", runner, sudo=True)


def deploy_to_pi(config: DeployConfig, runner: Runner = subprocess.run) -> Path:
    check_ssh(config, runner)

    ensure_remote_root(config, runner)
    render_env_file(config)
    sync_paths(config, runner)
    run_install(config, runner)

    check_docker(config, runner)
    check_opensearch(config, runner)

    build_image(config, runner)
    tar_path = save_image(config, runner)
    upload_and_load_image(config, tar_path, runner)

    enable_services(config, runner)
    start_compose_stack(config, runner)
    start_services(config, runner)
    return tar_path


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload/install flow for IDS2 on Raspberry Pi.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--repo-root", default=None, help="Repo root (defaults to config parent)")
    parser.add_argument("--pi-host", default=None, help="Pi hostname or IP")
    parser.add_argument("--pi-user", default="pi", help="Pi SSH user")
    parser.add_argument("--pi-port", type=int, default=22, help="Pi SSH port")
    parser.add_argument("--ssh-key", default=None, help="SSH private key path")
    parser.add_argument("--sudo-password", default=None, help="Sudo password (not recommended)")
    parser.add_argument("--remote-dir", default="/opt/ids2", help="Remote install directory")
    parser.add_argument("--image-name", default="ids2-agent", help="Docker image name")
    parser.add_argument("--image-tag", default="latest", help="Docker image tag")
    parser.add_argument("--dockerfile", default="Dockerfile", help="Dockerfile path")
    parser.add_argument("--opensearch-endpoint", default=None, help="OpenSearch endpoint URL")
    parser.add_argument("--include-tests", action="store_true", help="Sync tests directory")
    parser.add_argument(
        "--test-artifact", action="append", default=[], help="Extra test artifact paths"
    )
    parser.add_argument(
        "--sync-path", action="append", default=[], help="Override sync paths (relative)"
    )
    parser.add_argument("--skip-install", action="store_true", help="Skip install.sh on the Pi")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    config_path = Path(args.config).resolve()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else config_path.parent
    deploy_config = load_deploy_config(
        config_path,
        repo_root=repo_root,
        pi_host=args.pi_host,
        opensearch_endpoint=args.opensearch_endpoint,
        pi_user=args.pi_user,
        pi_port=args.pi_port,
        pi_ssh_key=Path(args.ssh_key) if args.ssh_key else None,
        sudo_password=args.sudo_password,
        remote_dir=Path(args.remote_dir),
        image_name=args.image_name,
        image_tag=args.image_tag,
        dockerfile=Path(args.dockerfile),
        include_tests=args.include_tests,
        test_artifacts=[Path(path) for path in args.test_artifact],
        sync_paths=[Path(path) for path in args.sync_path] if args.sync_path else None,
        run_install=not args.skip_install,
        verbose=args.verbose,
    )

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s - %(levelname)s - %(message)s")
    deploy_to_pi(deploy_config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
