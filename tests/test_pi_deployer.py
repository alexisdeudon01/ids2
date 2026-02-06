"""Tests for Raspberry Pi deployer."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "webbapp"))

from ids.deploy.config import DeployConfig
from ids.deploy.pi_deployer import PiDeployer


class _FakeSSH:
    def __init__(self):
        self.logs = []
        self.runs = []
        self.uploads = 0
        self.writes = []

    def _log(self, message: str) -> None:
        self.logs.append(message)

    def run(self, command: str, sudo: bool = False, check: bool = True) -> None:
        self.runs.append((command, sudo, check))

    def upload_directory(self, local_dir: Path, remote_dir: str) -> None:
        self.uploads += 1

    def write_file(self, remote_path: str, content: str, sudo: bool = False) -> None:
        self.writes.append((remote_path, sudo))


class TestPiDeployer(unittest.TestCase):
    def test_deploy_webapp_flow(self):
        config = DeployConfig(elastic_password="test")
        ssh = _FakeSSH()
        deployer = PiDeployer(ssh, config)

        deployer.deploy_webapp()

        self.assertEqual(ssh.uploads, 1)
        self.assertIn("📤 Uploading webapp files...", ssh.logs)
        self.assertIn("🐍 Installing webapp dependencies...", ssh.logs)
        self.assertIn("🧩 Configuring webapp service...", ssh.logs)
        self.assertIn("✅ Webapp deployed", ssh.logs)
