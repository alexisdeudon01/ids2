"""Raspberry Pi deployer."""

from __future__ import annotations

import json
import posixpath
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import DeployConfig
    from .ssh_client import SSHClient


class PiDeployer:
    """Deploy IDS components to Raspberry Pi."""
    
    def __init__(self, ssh: SSHClient, config: DeployConfig) -> None:
        self.ssh = ssh
        self.config = config

    def reset(self) -> None:
        """Clean Pi installation."""
        self.ssh._log("🧹 Resetting Pi...")
        self.ssh.run("systemctl disable --now webbapp ids suricata || true", sudo=True, check=False)
        self.ssh.run("rm -f /etc/systemd/system/webbapp.service /etc/systemd/system/ids.service", sudo=True, check=False)
        self.ssh.run("systemctl daemon-reload", sudo=True, check=False)
        self.ssh.run(f"rm -rf '{self.config.remote_dir}'", sudo=True, check=False)
        self.ssh.run("ufw --force reset", sudo=True, check=False)
        self.remove_docker()
        self.ssh.run("apt purge -y suricata || true", sudo=True, check=False)
        self.ssh.run("rm -rf /etc/suricata /var/log/suricata || true", sudo=True, check=False)
        self.ssh._log("✅ Reset complete")

    def install_docker(self) -> None:
        """Install Docker on Pi."""
        self.ssh._log("🐳 Installing Docker...")
        self.ssh.run("apt update && apt install -y docker.io docker-compose", sudo=True)
        self.ssh.run("systemctl enable --now docker", sudo=True)
        self.ssh._log("✅ Docker installed")

    def remove_docker(self) -> None:
        """Remove Docker from Pi."""
        self.ssh._log("🧹 Removing Docker...")
        self.ssh.run("apt purge -y docker.io docker-compose containerd runc || true", sudo=True, check=False)
        self.ssh.run("rm -rf /var/lib/docker /var/lib/containerd || true", sudo=True, check=False)
        self.ssh._log("✅ Docker removed")

    def install_probe(self) -> None:
        """Install Suricata probe."""
        self.ssh._log("📦 Installing probe dependencies...")
        self.ssh.run("apt update && apt install -y suricata python3-pip awscli ufw curl", sudo=True)
        self.ssh.run(
            "pip3 install --break-system-packages boto3 elasticsearch requests || pip3 install boto3 elasticsearch requests",
            sudo=True,
            check=False,
        )

        self.ssh._log("🛡️ Configuring network...")
        self.ssh.run(f"ip link set {self.config.mirror_interface} promisc on", sudo=True)
        self.ssh.run("ufw --force reset", sudo=True)
        self.ssh.run("ufw allow 22/tcp", sudo=True)
        self.ssh.run("ufw --force enable", sudo=True)

        self.ssh._log("📝 Configuring Suricata rules...")
        self.ssh.run(
            "echo 'alert icmp any any -> any any (msg:\"[IDS] ICMP DETECTED\"; sid:1000001; rev:1;)' "
            "| tee /etc/suricata/rules/local.rules",
            sudo=True,
        )
        self.ssh.run("chmod 644 /var/log/suricata/eve.json", sudo=True, check=False)
        self.ssh.run("systemctl enable --now suricata", sudo=True)
        self.ssh._log("✅ Probe ready")

    def deploy_webapp(self) -> None:
        """Deploy webapp to Pi."""
        self.upload_webapp_files()
        self.install_webapp_deps()
        self.configure_webapp_service()
        self.ssh._log("✅ Webapp deployed")

    def upload_webapp_files(self) -> None:
        """Upload webapp files to the Pi."""
        self.ssh._log("📤 Uploading webapp files...")
        local_dir = Path(__file__).parent.parent.parent.parent.parent
        self.ssh.run(f"mkdir -p '{self.config.remote_dir}'", sudo=True)
        self.ssh.run(f"chown -R {self.config.pi_user}:{self.config.pi_user} '{self.config.remote_dir}'", sudo=True)
        self.ssh.upload_directory(local_dir, self.config.remote_dir)

    def install_webapp_deps(self) -> None:
        """Install webapp Python dependencies on the Pi."""
        self.ssh._log("🐍 Installing webapp dependencies...")
        self.ssh.run("apt update && apt install -y python3-pip", sudo=True)
        self.ssh.run(
            f"cd '{self.config.remote_dir}' && "
            "python3 -m pip install --break-system-packages -r requirements.txt || python3 -m pip install -r requirements.txt",
            sudo=True,
        )

    def configure_webapp_service(self) -> None:
        """Configure and start the webapp service."""
        self.ssh._log("🧩 Configuring webapp service...")
        service = self._build_webapp_service()
        self.ssh.write_file("/etc/systemd/system/webbapp.service", service, sudo=True)
        self.ssh.run("systemctl daemon-reload", sudo=True)
        self.ssh.run("systemctl enable --now webbapp", sudo=True)

    def install_shared_ssh_key(self, local_key_path: str) -> None:
        """Upload shared SSH keypair to Pi (without overwriting)."""
        self.ssh._log("🔑 Installing shared SSH key on Pi...")
        private_path = Path(local_key_path).expanduser()
        public_path = Path(str(private_path) + ".pub")

        if not private_path.is_file():
            self.ssh._log(f"⚠️ SSH private key not found: {private_path}")
            return
        if not public_path.is_file():
            self.ssh._log(f"⚠️ SSH public key not found: {public_path}")
            return

        key_name = private_path.name
        remote_dir = f"/home/{self.config.pi_user}/.ssh"
        remote_key = posixpath.join(remote_dir, key_name)

        self.ssh.run(f"mkdir -p '{remote_dir}'", sudo=True)

        if not self.ssh.exists(remote_key):
            self.ssh.write_file(remote_key, private_path.read_text(encoding="utf-8"), sudo=True)
            self.ssh.run(f"chmod 600 '{remote_key}'", sudo=True)
        else:
            self.ssh._log(f"ℹ️ SSH key already exists on Pi: {remote_key}")

        if not self.ssh.exists(f"{remote_key}.pub"):
            self.ssh.write_file(
                f"{remote_key}.pub", public_path.read_text(encoding="utf-8"), sudo=True
            )
            self.ssh.run(f"chmod 644 '{remote_key}.pub'", sudo=True)

        public_key = public_path.read_text(encoding="utf-8").strip()
        if public_key:
            self.ssh.run(
                f"grep -qxF {json.dumps(public_key)} '{remote_dir}/authorized_keys' || "
                f"echo {json.dumps(public_key)} >> '{remote_dir}/authorized_keys'",
                sudo=True,
                check=False,
            )
        self.ssh.run(f"chmod 700 '{remote_dir}'", sudo=True, check=False)
        self.ssh.run(f"chmod 600 '{remote_dir}/authorized_keys'", sudo=True, check=False)
        self.ssh.run(f"chown -R {self.config.pi_user}:{self.config.pi_user} '{remote_dir}'", sudo=True)
        self.ssh._log("✅ Shared SSH key ready on Pi.")

    def install_streamer(self, elk_ip: str, elastic_password: str) -> None:
        """Install Suricata log streamer."""
        self.ssh._log("📡 Installing streamer...")
        service_path = posixpath.join(self.config.remote_dir, "streamer.py")
        
        streamer_script = self._build_streamer_script()
        self.ssh.write_file(service_path, streamer_script, sudo=False)
        self.ssh.run(f"chmod +x '{service_path}'", sudo=True)
        
        service = self._build_streamer_service(service_path, elk_ip, elastic_password)
        self.ssh.write_file("/etc/systemd/system/ids.service", service, sudo=True)
        self.ssh.run("systemctl daemon-reload", sudo=True)
        self.ssh.run("systemctl enable --now ids", sudo=True)
        self.ssh._log("✅ Streamer installed")

    def save_config(self, elk_ip: str) -> None:
        """Save deployment config to database."""
        self.ssh._log("💾 Saving configuration...")
        python_code = (
            "from db.database import Database; "
            "db = Database('db/ids.db'); "
            "db.save_deployment_config("
            f"{json.dumps(self.config.aws_region)}, "
            f"{json.dumps(elk_ip)}, "
            f"{json.dumps(self.config.elastic_password)}, "
            f"{json.dumps(self.config.pi_host)}, "
            f"{json.dumps(self.config.pi_user)}, "
            f"{json.dumps(self.config.pi_password)}, "
            f"{json.dumps(self.config.sudo_password)}, "
            f"{json.dumps(self.config.remote_dir)}, "
            f"{json.dumps(self.config.mirror_interface)}"
            ")"
        )
        self.ssh.run(f"cd '{self.config.remote_dir}' && python3 -c {json.dumps(python_code)}", sudo=True)

    def _build_webapp_service(self) -> str:
        return (
            "[Unit]\n"
            "Description=IDS Webapp API\n"
            "After=network.target\n\n"
            "[Service]\n"
            f"WorkingDirectory={self.config.remote_dir}\n"
            "ExecStart=/usr/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8000\n"
            "Environment=PYTHONUNBUFFERED=1\n"
            "Restart=always\n"
            f"User={self.config.pi_user}\n\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n"
        )

    def _build_streamer_service(self, service_path: str, ip: str, pwd: str) -> str:
        return (
            "[Unit]\n"
            "Description=IDS Streamer\n"
            "After=suricata.service\n\n"
            "[Service]\n"
            f"ExecStart=/usr/bin/python3 {service_path} {ip} {pwd}\n"
            "Restart=always\n"
            "User=root\n\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n"
        )

    def _build_streamer_script(self) -> str:
        return (
            "#!/usr/bin/env python3\n"
            "import json, os, sys, time\n"
            "from elasticsearch import Elasticsearch, helpers\n\n"
            "def main(ip, pwd):\n"
            "    es = Elasticsearch(f\"http://{ip}:9200\", basic_auth=(\"elastic\", pwd))\n"
            "    log_path = \"/var/log/suricata/eve.json\"\n"
            "    while True:\n"
            "        if os.path.exists(log_path) and os.path.getsize(log_path) > 0:\n"
            "            try:\n"
            "                with open(log_path, \"r+\", encoding=\"utf-8\") as f:\n"
            "                    lines = f.readlines()\n"
            "                    if lines:\n"
            "                        actions = []\n"
            "                        for line in lines:\n"
            "                            data = json.loads(line)\n"
            "                            if \"timestamp\" in data:\n"
            "                                data[\"@timestamp\"] = data.pop(\"timestamp\")\n"
            "                            data.pop(\"payload\", None)\n"
            "                            data.pop(\"payload_printable\", None)\n"
            "                            if \"flow\" in data:\n"
            "                                data[\"flow\"][\"total_bytes\"] = data[\"flow\"].get(\"bytes_toclient\", 0) + data[\"flow\"].get(\"bytes_toserver\", 0)\n"
            "                            actions.append({\"_index\": f\"suricata-{time.strftime('%Y.%m.%d')}\", \"_source\": data})\n"
            "                        helpers.bulk(es, actions)\n"
            "                        f.seek(0)\n"
            "                        f.truncate()\n"
            "            except: pass\n"
            "        time.sleep(1)\n\n"
            "if __name__ == \"__main__\":\n"
            "    if len(sys.argv) < 3: sys.exit(1)\n"
            "    main(sys.argv[1], sys.argv[2])\n"
        )
