#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
import time
import fcntl
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


REPO_ROOT = Path(__file__).resolve().parent
SRC_ROOT = REPO_ROOT / "src"
if SRC_ROOT.exists() and str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
elif not SRC_ROOT.exists():
    print(f"⚠️  Warning: SRC_ROOT {SRC_ROOT} does not exist. Some imports may fail.")

try:
    from ids.deploy import pi_uploader
except ImportError as e:  # pragma: no cover - optional import fallback
    pi_uploader = None
    if __name__ == "__main__":
        print(f"⚠️  Warning: Could not import ids.deploy.pi_uploader: {e}")


try:
    from ids.deploy import opensearch_domain
except ImportError as e:  # pragma: no cover - optional import fallback
    opensearch_domain = None
    if __name__ == "__main__":
        print(f"⚠️  Warning: Could not import ids.deploy.opensearch_domain: {e}")

try:
    from ids.config import ConfigManager
except ImportError as e:  # pragma: no cover - optional import fallback
    ConfigManager = None
    if __name__ == "__main__":
        print(f"⚠️  Warning: Could not import ids.config: {e}")

try:
    from ids.domain.exceptions import ErreurConfiguration
except ImportError as e:  # pragma: no cover - optional import fallback
    ErreurConfiguration = Exception
    if __name__ == "__main__":
        print(f"⚠️  Warning: Could not import ids.domain.exceptions: {e}")



@dataclass
class RepoPaths:
    root: Path
    config_path: Path
    secret_path: Path


@dataclass
class SSHConfig:
    host: str
    user: str
    port: int = 22
    key_path: Optional[Path] = None
    sudo_password: Optional[str] = None
    remote_dir: Path = Path(os.getenv("REMOTE_DIR", "/opt/ids-dashboard"))
    verbose: bool = False


def _ssh_options(config: SSHConfig) -> list[str]:
    options = [
        "-o",
        "ConnectTimeout=10",
        "-o",
        "StrictHostKeyChecking=accept-new",
    ]
    if config.key_path:
        options.extend(["-i", str(config.key_path)])
    return options


def _format_command(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def _rsync_ssh_command(config: SSHConfig) -> str:
    parts = ["ssh", "-p", str(config.port), *_ssh_options(config)]
    return " ".join(shlex.quote(part) for part in parts)


def run_local(
    command: list[str],
    *,
    check: bool = True,
    capture_output: bool = False,
    input_data: Optional[str] = None,
    verbose: bool = False,
) -> subprocess.CompletedProcess:
    if verbose:
        print(f"$ {_format_command(command)}")
    kwargs: Dict[str, Any] = {"text": True, "capture_output": capture_output, "check": check}
    if input_data is not None:
        kwargs["input"] = input_data
    return subprocess.run(command, **kwargs)


def run_ssh(
    config: SSHConfig,
    remote_command: str,
    *,
    check: bool = True,
    capture_output: bool = False,
    sudo: bool = False,
    input_data: Optional[str] = None,
) -> subprocess.CompletedProcess:
    # Test SSH connectivity before executing command
    # Skip BatchMode if key-based auth is not configured (password auth will be used)
    ssh_test_opts = ["-o", "ConnectTimeout=5"]
    if config.key_path and config.key_path.exists():
        ssh_test_opts.extend(["-o", "BatchMode=yes"])
    
    test_result = run_local(
        [
            "ssh",
            "-p",
            str(config.port),
            *ssh_test_opts,
            *_ssh_options(config),
            f"{config.user}@{config.host}",
            "echo 'SSH connection test'",
        ],
        check=False,
        capture_output=True,
    )
    if test_result.returncode != 0 and check:
        error_msg = f"Cannot connect to {config.user}@{config.host}:{config.port}."
        if test_result.stderr:
            error_msg += f" Error: {test_result.stderr[:200]}"
        else:
            error_msg += " Check connectivity and credentials."
        raise ConnectionError(error_msg)
    
    display_command = remote_command
    if sudo:
        remote_command = f"sh -lc {shlex.quote(remote_command)}"
        if config.sudo_password:
            remote_command = f"sudo -S -p '' {remote_command}"
            if input_data is None:
                input_data = f"{config.sudo_password}\n"
        else:
            remote_command = f"sudo -n {remote_command}"
    if config.verbose:
        suffix = " (sudo)" if sudo else ""
        print(f"[ssh] {config.user}@{config.host}: {display_command}{suffix}")
    command = [
        "ssh",
        "-p",
        str(config.port),
        *_ssh_options(config),
        f"{config.user}@{config.host}",
        remote_command,
    ]
    return run_local(
        command,
        check=check,
        capture_output=capture_output,
        input_data=input_data,
        verbose=config.verbose,
    )


def run_scp(config: SSHConfig, local_path: Path, remote_path: str) -> subprocess.CompletedProcess:
    if config.verbose:
        print(f"[scp] {local_path} -> {config.user}@{config.host}:{remote_path}")
    command = [
        "scp",
        "-P",
        str(config.port),
        *_ssh_options(config),
        str(local_path),
        f"{config.user}@{config.host}:{remote_path}",
    ]
    return run_local(command, check=True, capture_output=False, verbose=config.verbose)


def prompt_value(label: str, default: Optional[str]) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or (default or "")


def load_yaml_data(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError as e:
        logging.warning(f"yaml module not available: {e}")
        return {}
    except Exception as e:
        logging.warning(f"Unexpected error importing yaml: {e}")
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except yaml.YAMLError as e:
        logging.error(f"YAML parsing error in {path}: {e}")
        return {}
    except IOError as e:
        logging.error(f"IO error reading {path}: {e}")
        return {}
    except Exception as e:
        logging.error(f"Unexpected error reading {path}: {e}")
        return {}
    return data if isinstance(data, dict) else {}


def load_json_data(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle) or {}
    except json.JSONDecodeError as e:
        logging.error(f"JSON parsing error in {path}: {e}")
        return {}
    except IOError as e:
        logging.error(f"IO error reading {path}: {e}")
        return {}
    except Exception as e:
        logging.error(f"Unexpected error reading {path}: {e}")
        return {}
    return data if isinstance(data, dict) else {}


def load_pi_defaults(config_path: Path) -> dict[str, str]:
    data = load_yaml_data(config_path)
    raspberry = data.get("raspberry_pi", {}) if isinstance(data, dict) else {}
    host = ""
    user = ""
    if isinstance(raspberry, dict):
        host = raspberry.get("pi_ip") or raspberry.get("host") or ""
        user = raspberry.get("user") or raspberry.get("pi_user") or ""
    return {"host": host, "user": user}


def render_env_file(paths: RepoPaths) -> Optional[Path]:
    config_data = load_yaml_data(paths.config_path)
    secret_data = load_json_data(paths.secret_path)

    aws_config = config_data.get("aws", {}) if isinstance(config_data, dict) else {}
    opensearch = aws_config.get("opensearch", {}) if isinstance(aws_config, dict) else {}
    endpoint = aws_config.get("opensearch_endpoint") or opensearch.get("endpoint")
    region = aws_config.get("region")

    secret_aws = secret_data.get("aws", {}) if isinstance(secret_data, dict) else {}

    lines = []
    if secret_aws.get("access_key_id"):
        lines.append(f"AWS_ACCESS_KEY_ID={secret_aws['access_key_id']}")
    if secret_aws.get("secret_access_key"):
        lines.append(f"AWS_SECRET_ACCESS_KEY={secret_aws['secret_access_key']}")
    if region:
        lines.append(f"AWS_REGION={region}")
    if endpoint:
        lines.append(f"OPENSEARCH_ENDPOINT={endpoint}")

    if not lines:
        return None

    env_path = paths.root / "docker" / ".env"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return env_path


def ensure_remote_root(ssh_config: SSHConfig) -> None:
    remote_root = shlex.quote(str(ssh_config.remote_dir))
    owner = f"{ssh_config.user}:{ssh_config.user}"
    run_ssh(
        ssh_config,
        f"mkdir -p {remote_root} && chown -R {shlex.quote(owner)} {remote_root}",
        check=True,
        sudo=True,
    )


def ensure_env_on_pi(paths: RepoPaths, ssh_config: SSHConfig) -> None:
    env_path = render_env_file(paths)
    if env_path is None:
        print("No docker/.env generated (missing AWS values).")
        return
    ensure_remote_root(ssh_config)
    remote_env = ssh_config.remote_dir / "docker" / ".env"
    remote_dir = shlex.quote(str(remote_env.parent))
    run_ssh(ssh_config, f"mkdir -p {remote_dir}", check=True)
    run_scp(ssh_config, env_path, str(remote_env))
    print("docker/.env synced to Pi.")


def sync_endpoint_files(paths: RepoPaths, ssh_config: SSHConfig) -> bool:
    required = [
        paths.root / "docker" / "docker-compose.yml",
        paths.root / "docker" / "fastapi" / "Dockerfile",
        paths.root / "requirements.txt",
        paths.root / "src",
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        for path in missing:
            print(f"Missing required file: {path}")
        return False

    ensure_remote_root(ssh_config)
    entries = [
        (
            paths.root / "docker" / "docker-compose.yml",
            ssh_config.remote_dir / "docker" / "docker-compose.yml",
        ),
        (paths.root / "docker" / "fastapi", ssh_config.remote_dir / "docker" / "fastapi"),
        (paths.root / "requirements.txt", ssh_config.remote_dir / "requirements.txt"),
        (paths.root / "src", ssh_config.remote_dir / "src"),
    ]
    excludes = ["__pycache__", "*.pyc", ".venv", "dist"]
    for local_path, remote_path in entries:
        remote_parent = remote_path if local_path.is_dir() else remote_path.parent
        run_ssh(ssh_config, f"mkdir -p {shlex.quote(str(remote_parent))}", check=True)

        if shutil.which("rsync"):
            rsync_cmd = ["rsync", "-az", "--delete"]
            if ssh_config.verbose:
                rsync_cmd.append("--info=progress2")
            for exclude in excludes:
                rsync_cmd.extend(["--exclude", exclude])

            local_value = str(local_path)
            remote_value = str(remote_path)
            if local_path.is_dir():
                local_value = f"{local_value}/"
                remote_value = f"{remote_value}/"
            rsync_cmd.extend(
                [
                    "-e",
                    _rsync_ssh_command(ssh_config),
                    local_value,
                    f"{ssh_config.user}@{ssh_config.host}:{remote_value}",
                ]
            )
            run_local(rsync_cmd, check=True, verbose=ssh_config.verbose)
        else:
            if local_path.is_dir():
                scp_cmd = [
                    "scp",
                    "-r",
                    "-P",
                    str(ssh_config.port),
                    *_ssh_options(ssh_config),
                    str(local_path),
                    f"{ssh_config.user}@{ssh_config.host}:{remote_path}",
                ]
                run_local(scp_cmd, check=True, verbose=ssh_config.verbose)
            else:
                run_scp(ssh_config, local_path, str(remote_path))
    return True


def upload_to_pi(paths: RepoPaths, ssh_config: SSHConfig) -> None:
    if pi_uploader is None:
        print("pi_uploader module not available. Install deps and try again.")
        return
    deploy_config = pi_uploader.load_deploy_config(
        paths.config_path,
        repo_root=paths.root,
        pi_host=ssh_config.host,
        pi_user=ssh_config.user,
        pi_port=ssh_config.port,
        pi_ssh_key=ssh_config.key_path,
        remote_dir=ssh_config.remote_dir,
        sudo_password=ssh_config.sudo_password,
        verbose=ssh_config.verbose,
    )
    pi_uploader.deploy_to_pi(deploy_config)


def build_docker_and_run(paths: RepoPaths, ssh_config: SSHConfig) -> None:
    if pi_uploader is None:
        print("pi_uploader module not available. Install deps and try again.")
        return
    deploy_config = pi_uploader.load_deploy_config(
        paths.config_path,
        repo_root=paths.root,
        pi_host=ssh_config.host,
        pi_user=ssh_config.user,
        pi_port=ssh_config.port,
        pi_ssh_key=ssh_config.key_path,
        remote_dir=ssh_config.remote_dir,
        sudo_password=ssh_config.sudo_password,
        verbose=ssh_config.verbose,
    )
    pi_uploader.check_ssh(deploy_config)

    # Sync repo content to Pi so Docker builds happen remotely.
    pi_uploader.ensure_remote_root(deploy_config)
    pi_uploader.render_env_file(deploy_config)
    pi_uploader.sync_paths(deploy_config)

    try:
        pi_uploader.check_docker(deploy_config)
    except subprocess.CalledProcessError:
        print("Docker not available on Pi. Running install script...")
        pi_uploader.run_install(deploy_config)
        pi_uploader.check_docker(deploy_config)

    dockerfile = deploy_config.dockerfile
    dockerfile_arg = dockerfile.as_posix() if not dockerfile.is_absolute() else dockerfile.name
    image_ref = deploy_config.image_ref
    print("Building IDS2 Docker image on the Pi...")
    run_ssh(
        ssh_config,
        f"cd {shlex.quote(str(ssh_config.remote_dir))} && "
        f"DOCKER_BUILDKIT=1 docker build --network host -t {shlex.quote(image_ref)} "
        f"-f {shlex.quote(dockerfile_arg)} .",
        check=True,
        sudo=True,
    )

    pi_uploader.start_compose_stack(deploy_config)
    pi_uploader.start_services(deploy_config)
    print("Docker stack and services started on Pi.")


def check_services_on_pi(ssh_config: SSHConfig) -> None:
    services = [
        "ids2-agent.service",
        "suricata.service",
        "network-eth0-only.service",
    ]
    print("Systemd services:")
    for service in services:
        result = run_ssh(
            ssh_config,
            f"systemctl is-active {shlex.quote(service)}",
            check=False,
            capture_output=True,
            sudo=True,
        )
        status = (result.stdout or "").strip() or "unknown"
        print(f"- {service}: {status}")

    docker_dir = shlex.quote(str(ssh_config.remote_dir / "docker"))
    print("Docker compose status:")
    run_ssh(
        ssh_config,
        f"cd {docker_dir} && docker compose ps",
        check=False,
        sudo=True,
    )


def create_endpoint(paths: RepoPaths, ssh_config: SSHConfig) -> None:
    docker_dir_path = ssh_config.remote_dir / "docker"
    if not sync_endpoint_files(paths, ssh_config):
        print("Endpoint sync failed. Ensure the repo files are present locally.")
        return

    ensure_env_on_pi(paths, ssh_config)
    docker_dir = shlex.quote(str(docker_dir_path))
    print("Reinitializing FastAPI container...")
    run_ssh(
        ssh_config,
        f"cd {docker_dir} && docker compose stop fastapi || true",
        check=False,
        sudo=True,
    )
    run_ssh(
        ssh_config,
        f"cd {docker_dir} && docker compose rm -f -s fastapi || true",
        check=False,
        sudo=True,
    )

    print("Building FastAPI image on the Pi...")
    run_ssh(
        ssh_config,
        f"cd {shlex.quote(str(ssh_config.remote_dir))} && "
        "DOCKER_BUILDKIT=1 docker build --network host "
        "-t ids2-fastapi:latest -f docker/fastapi/Dockerfile .",
        check=True,
        sudo=True,
    )

    print("Starting FastAPI endpoint on the Pi...")
    run_ssh(
        ssh_config,
        f"cd {docker_dir} && docker compose up -d --force-recreate fastapi",
        check=True,
        sudo=True,
    )

    base_url = f"http://{ssh_config.host}:8080"
    print(f"Endpoint URLs: {base_url}/health , {base_url}/status")

    if wait_for_http(
        ssh_config,
        "http://localhost:8080/health",
        expected_code="200",
        timeout=30,
        show_progress=True,
    ):
        print("Endpoint health: ok")
        run_ssh(
            ssh_config,
            f"cd {docker_dir} && docker compose ps",
            check=False,
            sudo=True,
        )
        return

    print("Endpoint started, but health check failed.")
    run_ssh(
        ssh_config,
        f"cd {docker_dir} && docker compose ps",
        check=False,
        sudo=True,
    )
    run_ssh(
        ssh_config,
        f"cd {docker_dir} && docker compose logs --tail 50 fastapi",
        check=False,
        sudo=True,
    )


def test_pipeline(ssh_config: SSHConfig) -> None:
    result = run_ssh(
        ssh_config,
        "curl -sS http://localhost:8080/status",
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        print("Pipeline status check failed. Is the endpoint running?")
        return
    raw = (result.stdout or "").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print(raw)
        return

    state = data.get("etat_pipeline", "unknown")
    resume = data.get("resume", {}) if isinstance(data, dict) else {}
    total = resume.get("total", "n/a")
    healthy = resume.get("sains", "n/a")
    errors = resume.get("erreurs", "n/a")
    print(f"Pipeline state: {state} (healthy={healthy}/{total}, errors={errors})")


def wait_for_http(
    ssh_config: SSHConfig,
    url: str,
    *,
    expected_code: str = "200",
    timeout: int = 30,
    interval: float = 2.0,
    show_progress: bool = False,
) -> bool:
    start = time.monotonic()
    deadline = start + timeout
    last_len = 0
    while time.monotonic() < deadline:
        result = run_ssh(
            ssh_config,
            f"curl -sS -o /dev/null -w '%{{http_code}}' {shlex.quote(url)}",
            check=False,
            capture_output=True,
        )
        status = (result.stdout or "").strip()
        if result.returncode == 0 and status == expected_code:
            if show_progress:
                sys.stdout.write("\n")
                sys.stdout.flush()
            return True
        if show_progress:
            elapsed = time.monotonic() - start
            percent = min(1.0, elapsed / max(timeout, 1))
            bar_len = 24
            filled = int(bar_len * percent)
            bar = "#" * filled + "-" * (bar_len - filled)
            message = status or f"curl exit {result.returncode}"
            line = f"Waiting for {url} [{bar}] {int(percent * 100):3d}% ({message})"
            sys.stdout.write("\r" + line + (" " * max(0, last_len - len(line))))
            sys.stdout.flush()
            last_len = len(line)
        elif ssh_config.verbose:
            message = status or f"curl exit {result.returncode}"
            print(f"Waiting for {url} ({message})...")
        time.sleep(interval)
    if show_progress:
        sys.stdout.write("\n")
        sys.stdout.flush()
    return False


def _print_command_output(result: subprocess.CompletedProcess) -> None:
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    if stdout:
        print(stdout)
    if stderr:
        print(stderr)


def check_configuration(paths: RepoPaths, ssh_config: SSHConfig) -> None:
    print("Local configuration:")
    if not paths.config_path.exists():
        print(f"- Missing config file: {paths.config_path}")
        return

    if ConfigManager is not None:
        try:
            ConfigManager(str(paths.config_path), secret_path=str(paths.secret_path))
            print("- ConfigManager validation: OK")
        except ErreurConfiguration as exc:
            print(f"- ConfigManager validation error: {exc}")
        except Exception as exc:
            print(f"- ConfigManager load error: {exc}")
    else:
        print("- ConfigManager unavailable (missing dependencies).")

    config_data = load_yaml_data(paths.config_path)
    secret_data = load_json_data(paths.secret_path)

    aws_config = config_data.get("aws", {}) if isinstance(config_data, dict) else {}
    opensearch = aws_config.get("opensearch", {}) if isinstance(aws_config, dict) else {}
    endpoint = aws_config.get("opensearch_endpoint") or opensearch.get("endpoint")
    region = aws_config.get("region")
    instance_profile = bool(aws_config.get("credentials", {}).get("use_instance_profile"))

    secret_aws = secret_data.get("aws", {}) if isinstance(secret_data, dict) else {}
    access_key = secret_aws.get("access_key_id")
    secret_key = secret_aws.get("secret_access_key")

    print(f"- AWS region: {region or 'missing'}")
    print(f"- OpenSearch endpoint: {endpoint or 'missing'}")
    if instance_profile:
        print("- AWS credentials: instance profile enabled")
    else:
        creds_ok = bool(access_key and secret_key)
        print(f"- AWS credentials in secret.json: {'ok' if creds_ok else 'missing'}")

    required_paths = [
        "config.yaml",
        "deploy/ids2-agent.service",
        "deploy/suricata.service",
        "docker/docker-compose.yml",
        "vector/vector.toml",
        "suricata/suricata.yaml",
    ]
    for rel in required_paths:
        path = paths.root / rel
        status = "ok" if path.exists() else "missing"
        print(f"- {rel}: {status}")

    print("Remote configuration:")
    remote_checks = [
        "config.yaml",
        "deploy/ids2-agent.service",
        "deploy/suricata.service",
        "docker/docker-compose.yml",
        "vector/vector.toml",
        "suricata/suricata.yaml",
    ]
    for rel in remote_checks:
        remote_path = ssh_config.remote_dir / rel
        result = run_ssh(
            ssh_config,
            f"test -f {shlex.quote(str(remote_path))}",
            check=False,
        )
        status = "ok" if result.returncode == 0 else "missing"
        print(f"- {remote_path}: {status}")


def create_opensearch_domain(paths: RepoPaths) -> None:
    if opensearch_domain is None:
        print("opensearch_domain module not available. Install deps and try again.")
        return
    domain_name = input("OpenSearch domain name (leave blank to use config): ").strip() or None
    response = opensearch_domain.creer_domaine(
        str(paths.config_path),
        secret_path=str(paths.secret_path),
        domain_name=domain_name,
        wait=True,
        timeout=1800,
        poll=30,
        apply_endpoint=True,
    )
    endpoint = None
    if isinstance(response, dict):
        status = response.get("DomainStatus", {})
        if isinstance(status, dict):
            endpoint = status.get("Endpoint") or (status.get("Endpoints", {}) or {}).get("vpc")
    if endpoint:
        print(f"OpenSearch endpoint: {endpoint}")
    else:
        print(
            "OpenSearch domain requested. Endpoint will be written to config.yaml when available."
        )


def menu(paths: RepoPaths, ssh_config: SSHConfig) -> None:
    options = (
        "1. Upload to Pi",
        "2. Build docker and run",
        "3. Check all services on Pi",
        "4. Create the endpoint",
        "5. Test the pipeline",
        "6. Check all configuration",
        "7. Create OpenSearch domain",
        "q. Quit",
    )

    def run_action(label: str, action) -> None:
        try:
            action()
        except subprocess.CalledProcessError as exc:
            print(f"{label} failed (exit {exc.returncode}).")
        except Exception as exc:
            print(f"{label} failed: {exc}")

    while True:
        print("\nMain menu:")
        for line in options:
            print(line)
        choice = input("Select option: ").strip().lower()
        if choice == "1":
            run_action("Upload", lambda: upload_to_pi(paths, ssh_config))
        elif choice == "2":
            run_action("Build/run", lambda: build_docker_and_run(paths, ssh_config))
        elif choice == "3":
            run_action("Check services", lambda: check_services_on_pi(ssh_config))
        elif choice == "4":
            run_action("Create endpoint", lambda: create_endpoint(paths, ssh_config))
        elif choice == "5":
            run_action("Test pipeline", lambda: test_pipeline(ssh_config))
        elif choice == "6":
            run_action("Check configuration", lambda: check_configuration(paths, ssh_config))
        elif choice == "7":
            run_action("Create OpenSearch domain", lambda: create_opensearch_domain(paths))
        elif choice in {"q", "quit", "exit"}:
            return
        else:
            print("Invalid choice.")


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IDS2 Pi control menu.")
    parser.add_argument("--pi-host", default=None, help="Pi IP or hostname")
    parser.add_argument("--pi-user", default=None, help="Pi SSH user")
    parser.add_argument("--pi-port", type=int, default=22, help="Pi SSH port")
    parser.add_argument("--ssh-key", default=None, help="SSH private key path")
    parser.add_argument("--remote-dir", default="/opt/ids2", help="Pi install directory")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--secret", default="secret.json", help="Path to secret.json")
    parser.add_argument("--sudo-password", default=None, help="Sudo password (not recommended)")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    config_path = (
        (REPO_ROOT / args.config).resolve()
        if not Path(args.config).is_absolute()
        else Path(args.config)
    )
    secret_path = (
        (REPO_ROOT / args.secret).resolve()
        if not Path(args.secret).is_absolute()
        else Path(args.secret)
    )

    defaults = load_pi_defaults(config_path)
    host_default = args.pi_host or defaults.get("host") or ""
    user_default = args.pi_user or defaults.get("user") or "pi"

    host = prompt_value("Pi host/IP", host_default)
    user = prompt_value("Pi user", user_default)
    sudo_password = args.sudo_password
    if sudo_password is None:
        sudo_password = (
            getpass.getpass("Sudo password (leave empty if not needed): ").strip() or None
        )

    if not host:
        print("Pi host is required.")
        return 1

    # Validate remote directory path
    remote_dir_path = Path(args.remote_dir)
    if not remote_dir_path.is_absolute():
        logging.warning(f"Remote directory '{remote_dir_path}' is not absolute. Using as-is.")
    
    ssh_config = SSHConfig(
        host=host,
        user=user or "pi",
        port=args.pi_port,
        key_path=Path(args.ssh_key).expanduser() if args.ssh_key else None,
        sudo_password=sudo_password,
        remote_dir=remote_dir_path,
        verbose=args.verbose,
    )
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
    paths = RepoPaths(root=REPO_ROOT, config_path=config_path, secret_path=secret_path)
    menu(paths, ssh_config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
