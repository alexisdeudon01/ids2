"""Tests for SSH client."""

import importlib
import json
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "webbapp"))


class TestSSHClient(unittest.TestCase):
    """Validate SSH client behavior with mocked paramiko."""

    def _load_module(self):
        fake_client = mock.MagicMock()
        fake_paramiko = types.SimpleNamespace(
            SSHClient=mock.MagicMock(return_value=fake_client),
            AutoAddPolicy=mock.MagicMock(return_value="policy"),
        )

        with mock.patch.dict(sys.modules, {"paramiko": fake_paramiko}):
            sys.modules.pop("ids.deploy.ssh_client", None)
            module = importlib.import_module("ids.deploy.ssh_client")

        return module, fake_client

    def test_connect_and_open_sftp(self):
        module, fake_client = self._load_module()
        fake_sftp = mock.MagicMock()
        fake_client.open_sftp.return_value = fake_sftp

        ssh = module.SSHClient("host", "user", "pass", "sudo", lambda msg: None)

        fake_client.connect.assert_called_once_with(
            hostname="host",
            username="user",
            password="pass",
            key_filename=None,
            allow_agent=True,
            look_for_keys=True,
            timeout=20,
        )
        fake_client.open_sftp.assert_called_once()

        ssh.close()
        fake_sftp.close.assert_called_once()
        fake_client.close.assert_called_once()

    def test_run_wraps_sudo(self):
        module, _ = self._load_module()
        ssh = module.SSHClient.__new__(module.SSHClient)
        with mock.patch.object(module.SSHClient, "_exec", return_value=(0, "", "")) as exec_mock:
            ssh.run("echo hello", sudo=True)

        expected = f"sudo -S -p '' bash -lc {json.dumps('echo hello')}"
        exec_mock.assert_called_once_with(expected)

    def test_run_raises_on_failure(self):
        module, _ = self._load_module()
        ssh = module.SSHClient.__new__(module.SSHClient)
        with mock.patch.object(module.SSHClient, "_exec", return_value=(1, "", "")):
            with self.assertRaises(RuntimeError):
                ssh.run("false", sudo=False, check=True)

    def test_connect_with_key_path(self):
        module, fake_client = self._load_module()
        fake_sftp = mock.MagicMock()
        fake_client.open_sftp.return_value = fake_sftp

        key_path = "~/.ssh/pi_key"
        with mock.patch.object(module.Path, "is_file", return_value=True):
            module.SSHClient("host", "user", "", "sudo", lambda msg: None, ssh_key_path=key_path)

        fake_client.connect.assert_called_once_with(
            hostname="host",
            username="user",
            password=None,
            key_filename=os.path.expanduser(key_path),
            allow_agent=True,
            look_for_keys=True,
            timeout=20,
        )
