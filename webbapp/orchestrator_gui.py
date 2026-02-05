"""Tkinter GUI orchestrator for AWS + Pi2 deployment."""

from __future__ import annotations

import io
import json
import os
import posixpath
import queue
import threading
import time
import tkinter as tk
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk
import uuid

import boto3
import paramiko
import requests
from elasticsearch import Elasticsearch, helpers


class SuricataMaster:
    """Deploy ELK on AWS and stream Suricata logs."""

    def __init__(self, region: str, es_pwd: str, log) -> None:
        self.region = region
        self.es_pwd = es_pwd
        self.log_path = "/var/log/suricata/eve.json"
        self.ec2 = boto3.resource("ec2", region_name=region)
        self._log = log

    def deploy_aws(self) -> str:
        self._log("☁️ Déploiement EC2 + ELK (Full Metadata)...")
        my_ip = (
            urllib.request.urlopen("https://checkip.amazonaws.com")
            .read()
            .decode("utf-8")
            .strip()
        )
        sg = self.ec2.create_security_group(
            GroupName=f"ids-sg-{int(time.time())}",
            Description="IDS Access",
        )
        sg.authorize_ingress(IpProtocol="tcp", FromPort=9200, ToPort=9200, CidrIp=f"{my_ip}/32")
        sg.authorize_ingress(IpProtocol="tcp", FromPort=5601, ToPort=5601, CidrIp=f"{my_ip}/32")

        compose = (
            "version: '3.8'\n"
            "services:\n"
            "  elasticsearch:\n"
            "    image: docker.elastic.co/elasticsearch/elasticsearch:8.12.0\n"
            "    environment: [discovery.type=single-node, xpack.security.enabled=true, "
            f"ELASTIC_PASSWORD={self.es_pwd}, 'ES_JAVA_OPTS=-Xms2g -Xmx2g']\n"
            "    ports: ['9200:9200']\n"
            "  kibana:\n"
            "    image: docker.elastic.co/kibana/kibana:8.12.0\n"
            "    ports: ['5601:5601']\n"
            "    depends_on: [elasticsearch]\n"
            "    environment: [ELASTICSEARCH_HOSTS=http://elasticsearch:9200, "
            f"ELASTICSEARCH_USERNAME=elastic, ELASTICSEARCH_PASSWORD={self.es_pwd}]"
        )

        user_data = (
            "#!/bin/bash\n"
            "apt update && apt install -y docker.io docker-compose\n"
            "sysctl -w vm.max_map_count=262144\n"
            "mkdir -p /home/ubuntu/elk && echo \""
            + compose.replace('"', '\\"')
            + "\" > /home/ubuntu/elk/docker-compose.yml\n"
            "cd /home/ubuntu/elk && docker-compose up -d"
        )

        instances = self.ec2.create_instances(
            ImageId="ami-00c71bd4d220aa22a",
            InstanceType="t3.medium",
            MinCount=1,
            MaxCount=1,
            SecurityGroupIds=[sg.id],
            UserData=user_data,
        )
        instance = instances[0]
        instance.wait_until_running()
        instance.reload()
        return instance.public_ip_address

    def configure_es_mapping(self, ip: str) -> None:
        self._log("📊 Configuration Mapping (IP/Flow/Alert) & Rétention...")
        time.sleep(180)
        es = Elasticsearch(f"http://{ip}:9200", basic_auth=("elastic", self.es_pwd))

        es.ilm.put_lifecycle(
            name="ids-retention",
            body={
                "policy": {
                    "phases": {
                        "hot": {"actions": {"rollover": {"max_age": "1d"}}},
                        "delete": {"min_age": "7d", "actions": {"delete": {}}},
                    }
                }
            },
        )
        es.indices.put_index_template(
            name="ids-template",
            body={
                "index_patterns": ["suricata-*"],
                "template": {
                    "settings": {"index.lifecycle.name": "ids-retention"},
                    "mappings": {
                        "properties": {
                            "@timestamp": {"type": "date"},
                            "src_ip": {"type": "ip"},
                            "dest_ip": {"type": "ip"},
                            "src_port": {"type": "integer"},
                            "dest_port": {"type": "integer"},
                            "proto": {"type": "keyword"},
                            "event_type": {"type": "keyword"},
                            "flow.total_bytes": {"type": "long"},
                            "alert.severity": {"type": "integer"},
                            "alert.signature": {"type": "keyword"},
                        }
                    },
                },
            },
        )
        requests.post(
            f"http://{ip}:5601/api/data_views/data_view",
            auth=("elastic", self.es_pwd),
            json={"data_view": {"title": "suricata-*", "name": "Suricata Full Specs", "timeFieldName": "@timestamp"}},
            headers={"kbn-xsrf": "true"},
            timeout=10,
        )

    @staticmethod
    def build_systemd_service(service_path: str, ip: str, pwd: str) -> str:
        return (
            "[Unit]\n"
            "Description=IDS-Full-Meta-Streamer\n"
            "After=suricata.service\n"
            "\n"
            "[Service]\n"
            f"ExecStart=/usr/bin/python3 {service_path} {ip} {pwd}\n"
            "Restart=always\n"
            "User=root\n"
            "\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n"
        )


@dataclass
class DeployConfig:
    aws_region: str
    elastic_password: str
    pi_host: str
    pi_user: str
    pi_password: str
    sudo_password: str
    remote_dir: str
    mirror_interface: str
    reset_first: bool
    install_docker: bool
    remove_docker: bool


class SSHSession:
    def __init__(self, host: str, user: str, password: str, sudo_password: str, log) -> None:
        self.host = host
        self.user = user
        self.password = password
        self.sudo_password = sudo_password
        self._log = log
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(hostname=host, username=user, password=password, timeout=20)
        self.sftp = self.client.open_sftp()

    def close(self) -> None:
        self.sftp.close()
        self.client.close()

    def _exec(self, command: str) -> tuple[int, str, str]:
        stdin, stdout, stderr = self.client.exec_command(command)
        if command.startswith("sudo -S"):
            stdin.write(self.sudo_password + "\n")
            stdin.flush()
        out_lines = []
        err_lines = []
        for line in iter(stdout.readline, ""):
            if line:
                out_lines.append(line)
                self._log(line.rstrip())
        for line in iter(stderr.readline, ""):
            if line:
                err_lines.append(line)
                self._log(line.rstrip())
        exit_status = stdout.channel.recv_exit_status()
        return exit_status, "".join(out_lines), "".join(err_lines)

    def run(self, command: str, sudo: bool = False, check: bool = True) -> None:
        wrapped = f"bash -lc {json.dumps(command)}"
        if sudo:
            wrapped = f"sudo -S -p '' {wrapped}"
        exit_status, _, _ = self._exec(wrapped)
        if check and exit_status != 0:
            raise RuntimeError(f"Commande distante échouée ({exit_status}): {command}")

    def write_remote_file(self, remote_path: str, content: str, sudo: bool = False) -> None:
        tmp_path = f"/tmp/{uuid.uuid4().hex}.tmp"
        with io.BytesIO(content.encode("utf-8")) as buff:
            self.sftp.putfo(buff, tmp_path)
        if sudo:
            self.run(f"mv '{tmp_path}' '{remote_path}'", sudo=True)
        else:
            self.run(f"mv '{tmp_path}' '{remote_path}'", sudo=False)

    def put_dir(self, local_dir: Path, remote_dir: str) -> None:
        ignore_dirs = {".venv", "__pycache__", "node_modules", ".git"}
        ignore_files = {"ids.db"}
        for root, dirs, files in os.walk(local_dir):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            rel_path = Path(root).relative_to(local_dir)
            remote_path = posixpath.join(remote_dir, str(rel_path))
            self.run(f"mkdir -p '{remote_path}'", sudo=False)
            for name in files:
                if name in ignore_files:
                    continue
                local_file = Path(root) / name
                remote_file = posixpath.join(remote_path, name)
                self.sftp.put(str(local_file), remote_file)


class OrchestratorGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("IDS2 - Orchestrateur Pi2 + AWS")
        self.geometry("960x720")
        self.resizable(True, True)
        self.log_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.worker: threading.Thread | None = None

        self._build_ui()
        self.after(200, self._process_log_queue)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        main = ttk.Frame(self, padding=12)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)

        creds = ttk.LabelFrame(main, text="Credentials & Cibles", padding=10)
        creds.grid(row=0, column=0, sticky="ew")
        for idx in range(2):
            creds.columnconfigure(idx, weight=1)

        self.aws_region = self._add_entry(creds, "AWS Region", 0, "eu-west-1")
        self.elastic_password = self._add_entry(creds, "Elastic Password", 1, "", show=True)
        self.pi_host = self._add_entry(creds, "Pi2 Host/IP", 2, "")
        self.pi_user = self._add_entry(creds, "Pi2 User", 3, "pi")
        self.pi_password = self._add_entry(creds, "Pi2 Password", 4, "", show=True)
        self.sudo_password = self._add_entry(creds, "Pi2 Sudo Password", 5, "", show=True)
        self.remote_dir = self._add_entry(creds, "Remote Dir", 6, "/opt/webbapp")
        self.mirror_interface = self._add_entry(creds, "Mirror Interface", 7, "eth0")

        self.reset_var = tk.BooleanVar(value=False)
        reset_check = ttk.Checkbutton(
            creds,
            text="Reset complet (suppression services, docker, scripts)",
            variable=self.reset_var,
        )
        reset_check.grid(row=8, column=0, columnspan=2, sticky="w", pady=(8, 0))

        self.install_docker_var = tk.BooleanVar(value=False)
        install_docker_check = ttk.Checkbutton(
            creds,
            text="Installer Docker sur Pi2 (optionnel)",
            variable=self.install_docker_var,
        )
        install_docker_check.grid(row=9, column=0, columnspan=2, sticky="w")

        self.remove_docker_var = tk.BooleanVar(value=False)
        remove_docker_check = ttk.Checkbutton(
            creds,
            text="Supprimer Docker sur Pi2 (optionnel)",
            variable=self.remove_docker_var,
        )
        remove_docker_check.grid(row=10, column=0, columnspan=2, sticky="w")

        action_frame = ttk.Frame(main)
        action_frame.grid(row=1, column=0, sticky="ew", pady=10)
        action_frame.columnconfigure(3, weight=1)

        self.deploy_button = ttk.Button(action_frame, text="Déployer", command=self.start_deploy)
        self.deploy_button.grid(row=0, column=0, padx=(0, 10))

        self.reset_button = ttk.Button(action_frame, text="Reset uniquement", command=self.start_reset_only)
        self.reset_button.grid(row=0, column=1, sticky="w", padx=(0, 10))

        self.install_docker_button = ttk.Button(
            action_frame, text="Installer Docker", command=self.start_install_docker_only
        )
        self.install_docker_button.grid(row=0, column=2, sticky="w", padx=(0, 10))

        self.remove_docker_button = ttk.Button(
            action_frame, text="Supprimer Docker", command=self.start_remove_docker_only
        )
        self.remove_docker_button.grid(row=0, column=3, sticky="w")

        self.progress_label = ttk.Label(action_frame, text="Idle")
        self.progress_label.grid(row=0, column=4, sticky="e")

        self.progress = ttk.Progressbar(main, mode="determinate")
        self.progress.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        log_frame = ttk.LabelFrame(main, text="Logs", padding=10)
        log_frame.grid(row=3, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, height=20, wrap="word")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.config(yscrollcommand=scrollbar.set)

    def _add_entry(self, parent: ttk.LabelFrame, label: str, row: int, default: str, show: bool = False) -> ttk.Entry:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
        entry = ttk.Entry(parent, show="*" if show else "")
        entry.insert(0, default)
        entry.grid(row=row, column=1, sticky="ew", pady=4)
        return entry

    def log(self, message: str) -> None:
        self.log_queue.put(("log", message))

    def set_progress(self, value: float, label: str) -> None:
        self.log_queue.put(("progress", f"{value}|{label}"))

    def _process_log_queue(self) -> None:
        while not self.log_queue.empty():
            kind, payload = self.log_queue.get()
            if kind == "log":
                self.log_text.insert("end", payload + "\n")
                self.log_text.see("end")
            elif kind == "progress":
                value_str, label = payload.split("|", 1)
                self.progress["value"] = float(value_str)
                self.progress_label.config(text=label)
        self.after(200, self._process_log_queue)

    def _collect_config(self, reset_override: bool | None = None) -> DeployConfig:
        reset_first = self.reset_var.get() if reset_override is None else reset_override
        return DeployConfig(
            aws_region=self.aws_region.get().strip(),
            elastic_password=self.elastic_password.get().strip(),
            pi_host=self.pi_host.get().strip(),
            pi_user=self.pi_user.get().strip(),
            pi_password=self.pi_password.get().strip(),
            sudo_password=self.sudo_password.get().strip(),
            remote_dir=self.remote_dir.get().strip(),
            mirror_interface=self.mirror_interface.get().strip(),
            reset_first=reset_first,
            install_docker=self.install_docker_var.get(),
            remove_docker=self.remove_docker_var.get(),
        )

    def start_deploy(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        config = self._collect_config()
        if not config.pi_host or not config.pi_user:
            messagebox.showerror("Erreur", "Pi2 Host/IP et utilisateur sont requis.")
            return
        if not config.aws_region or not config.elastic_password:
            messagebox.showerror("Erreur", "AWS Region et Elastic Password sont requis.")
            return
        self._start_worker(lambda: self._run_deploy(config))

    def start_reset_only(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        config = self._collect_config(reset_override=True)
        if not config.pi_host or not config.pi_user:
            messagebox.showerror("Erreur", "Pi2 Host/IP et utilisateur sont requis.")
            return
        self._start_worker(lambda: self._run_reset_only(config))

    def start_install_docker_only(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        config = self._collect_config(reset_override=False)
        if not config.pi_host or not config.pi_user:
            messagebox.showerror("Erreur", "Pi2 Host/IP et utilisateur sont requis.")
            return
        self._start_worker(lambda: self._run_install_docker(config))

    def start_remove_docker_only(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        config = self._collect_config(reset_override=False)
        if not config.pi_host or not config.pi_user:
            messagebox.showerror("Erreur", "Pi2 Host/IP et utilisateur sont requis.")
            return
        self._start_worker(lambda: self._run_remove_docker(config))

    def _start_worker(self, target) -> None:
        self.deploy_button.config(state="disabled")
        self.reset_button.config(state="disabled")
        self.install_docker_button.config(state="disabled")
        self.remove_docker_button.config(state="disabled")
        self.progress["value"] = 0
        self.log_text.delete("1.0", "end")
        self.worker = threading.Thread(target=target, daemon=True)
        self.worker.start()

    def _finish_worker(self) -> None:
        self.deploy_button.config(state="normal")
        self.reset_button.config(state="normal")
        self.install_docker_button.config(state="normal")
        self.remove_docker_button.config(state="normal")

    def _run_reset_only(self, config: DeployConfig) -> None:
        try:
            self.set_progress(5, "Connexion Pi2")
            with self._ssh_session(config) as ssh:
                self._reset_remote(ssh, config)
            self.set_progress(100, "Reset terminé")
        except Exception as exc:
            self.log(f"❌ Erreur reset: {exc}")
            self.set_progress(0, "Erreur")
        finally:
            self._finish_worker()

    def _run_install_docker(self, config: DeployConfig) -> None:
        try:
            self.set_progress(10, "Connexion Pi2")
            with self._ssh_session(config) as ssh:
                self._install_docker(ssh)
            self.set_progress(100, "Docker installé")
        except Exception as exc:
            self.log(f"❌ Erreur docker: {exc}")
            self.set_progress(0, "Erreur")
        finally:
            self._finish_worker()

    def _run_remove_docker(self, config: DeployConfig) -> None:
        try:
            self.set_progress(10, "Connexion Pi2")
            with self._ssh_session(config) as ssh:
                self._remove_docker(ssh)
            self.set_progress(100, "Docker supprimé")
        except Exception as exc:
            self.log(f"❌ Erreur suppression docker: {exc}")
            self.set_progress(0, "Erreur")
        finally:
            self._finish_worker()

    def _run_deploy(self, config: DeployConfig) -> None:
        try:
            step = 0
            total_steps = 7
            if config.reset_first:
                total_steps += 1
            if config.remove_docker:
                total_steps += 1
            if config.install_docker:
                total_steps += 1

            def advance(label: str) -> None:
                nonlocal step
                step += 1
                self.set_progress(step / total_steps * 100, label)

            with self._ssh_session(config) as ssh:
                advance("Connexion Pi2")
                if config.reset_first:
                    self._reset_remote(ssh, config)
                    advance("Reset complet")

                if config.remove_docker:
                    self._remove_docker(ssh)
                    advance("Suppression Docker")

                if config.install_docker:
                    self._install_docker(ssh)
                    advance("Installation Docker")

                advance("Déploiement AWS")
                master = SuricataMaster(config.aws_region, config.elastic_password, log=self.log)
                elk_ip = master.deploy_aws()

                advance("Configuration ES")
                master.configure_es_mapping(elk_ip)

                advance("Installation sonde Pi2")
                self._install_probe(ssh, config)

                advance("Déploiement WebApp2")
                self._deploy_webapp2(ssh, config)

                advance("Streamer Suricata")
                self._install_streamer_service(ssh, config, elk_ip)

                advance("Sauvegarde config")
                self._save_config(ssh, config, elk_ip)

            self.set_progress(100, "Déploiement terminé")
            self.log(f"✅ Dashboard Kibana: http://{elk_ip}:5601")
        except Exception as exc:
            self.log(f"❌ Erreur déploiement: {exc}")
            self.set_progress(0, "Erreur")
        finally:
            self._finish_worker()

    def _ssh_session(self, config: DeployConfig):
        class _Session:
            def __init__(self, outer):
                self.outer = outer
                self.session = None

            def __enter__(self):
                self.session = SSHSession(
                    config.pi_host,
                    config.pi_user,
                    config.pi_password,
                    config.sudo_password,
                    self.outer.log,
                )
                return self.session

            def __exit__(self, exc_type, exc, tb):
                if self.session:
                    self.session.close()

        return _Session(self)

    def _reset_remote(self, ssh: SSHSession, config: DeployConfig) -> None:
        self.log("🧹 Reset complet en cours...")
        ssh.run("systemctl disable --now webbapp || true", sudo=True, check=False)
        ssh.run("systemctl disable --now ids || true", sudo=True, check=False)
        ssh.run("systemctl disable --now suricata || true", sudo=True, check=False)
        ssh.run("rm -f /etc/systemd/system/webbapp.service /etc/systemd/system/ids.service", sudo=True, check=False)
        ssh.run("systemctl daemon-reload", sudo=True, check=False)
        ssh.run(f"rm -rf '{config.remote_dir}'", sudo=True, check=False)
        ssh.run("ufw --force reset", sudo=True, check=False)
        self._remove_docker(ssh)
        ssh.run("apt purge -y suricata || true", sudo=True, check=False)
        ssh.run("rm -rf /etc/suricata /var/log/suricata || true", sudo=True, check=False)
        ssh.run("pip3 uninstall -y boto3 elasticsearch requests || true", sudo=True, check=False)
        self.log("✅ Reset complet terminé.")

    def _install_docker(self, ssh: SSHSession) -> None:
        self.log("🐳 Installation Docker...")
        ssh.run("apt update && apt install -y docker.io docker-compose", sudo=True, check=False)
        ssh.run("systemctl enable --now docker", sudo=True, check=False)
        self.log("✅ Docker installé.")

    def _remove_docker(self, ssh: SSHSession) -> None:
        self.log("🧹 Suppression Docker...")
        ssh.run("apt purge -y docker.io docker-compose containerd runc || true", sudo=True, check=False)
        ssh.run("rm -rf /var/lib/docker /var/lib/containerd || true", sudo=True, check=False)
        self.log("✅ Docker supprimé.")

    def _install_probe(self, ssh: SSHSession, config: DeployConfig) -> None:
        self.log("📦 Installation des dépendances sonde...")
        ssh.run("apt update && apt install -y suricata python3-pip awscli ufw curl", sudo=True)
        ssh.run("pip3 install --break-system-packages boto3 elasticsearch requests", sudo=True, check=False)

        self.log("🛡️ Configuration réseau & furtivité...")
        ssh.run(f"ip link set {config.mirror_interface} promisc on", sudo=True)
        ssh.run("ufw --force reset", sudo=True)
        ssh.run("ufw allow 22/tcp", sudo=True)
        ssh.run("ufw --force enable", sudo=True)

        self.log("📝 Injection des règles...")
        ssh.run(
            "echo 'alert icmp any any -> any any (msg:\"[IDS] ICMP DETECTE\"; sid:1000001; rev:1;)' "
            "| tee /etc/suricata/rules/local.rules",
            sudo=True,
        )
        ssh.run("chmod 644 /var/log/suricata/eve.json", sudo=True, check=False)
        ssh.run(\"sed -i 's/payload: yes/payload: no/g' /etc/suricata/suricata.yaml\", sudo=True, check=False)
        ssh.run("systemctl enable --now suricata", sudo=True)
        self.log("✅ Sonde prête.")

    def _deploy_webapp2(self, ssh: SSHSession, config: DeployConfig) -> None:
        local_dir = Path(__file__).parent
        ssh.run(f"mkdir -p '{config.remote_dir}'", sudo=True)
        ssh.run(f"chown -R {config.pi_user}:{config.pi_user} '{config.remote_dir}'", sudo=True)
        ssh.put_dir(local_dir, config.remote_dir)
        ssh.run("apt update && apt install -y python3-pip", sudo=True)
        ssh.run(
            f"cd '{config.remote_dir}' && "
            "python3 -m pip install --break-system-packages -r requirements.txt "
            "|| python3 -m pip install -r requirements.txt",
            sudo=True,
        )

        service = (
            "[Unit]\n"
            "Description=IDS Webbapp API\n"
            "After=network.target\n\n"
            "[Service]\n"
            f"WorkingDirectory={config.remote_dir}\n"
            "ExecStart=/usr/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8000\n"
            "Environment=PYTHONUNBUFFERED=1\n"
            "Restart=always\n"
            f"User={config.pi_user}\n\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n"
        )
        ssh.write_remote_file("/etc/systemd/system/webbapp.service", service, sudo=True)
        ssh.run("systemctl daemon-reload", sudo=True)
        ssh.run("systemctl enable --now webbapp", sudo=True)

    def _build_streamer_script(self) -> str:
        return (
            "#!/usr/bin/env python3\n"
            "import json\n"
            "import os\n"
            "import sys\n"
            "import time\n"
            "from elasticsearch import Elasticsearch, helpers\n\n"
            "def main(ip, pwd):\n"
            "    es = Elasticsearch(f\"http://{ip}:9200\", basic_auth=(\"elastic\", pwd))\n"
            "    log_path = \"/var/log/suricata/eve.json\"\n"
            "    while True:\n"
            "        if os.path.exists(log_path) and os.path.getsize(log_path) > 0:\n"
            "            try:\n"
            "                with open(log_path, \"r+\", encoding=\"utf-8\") as handle:\n"
            "                    lines = handle.readlines()\n"
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
            "                        handle.seek(0)\n"
            "                        handle.truncate()\n"
            "            except Exception:\n"
            "                pass\n"
            "        time.sleep(1)\n\n"
            "if __name__ == \"__main__\":\n"
            "    if len(sys.argv) < 3:\n"
            "        sys.exit(1)\n"
            "    main(sys.argv[1], sys.argv[2])\n"
        )

    def _install_streamer_service(self, ssh: SSHSession, config: DeployConfig, elk_ip: str) -> None:
        service_path = posixpath.join(config.remote_dir, "streamer.py")
        ssh.write_remote_file(service_path, self._build_streamer_script(), sudo=False)
        ssh.run(f"chmod +x '{service_path}'", sudo=True)
        service = SuricataMaster.build_systemd_service(service_path, elk_ip, config.elastic_password)
        ssh.write_remote_file("/etc/systemd/system/ids.service", service, sudo=True)
        ssh.run("systemctl daemon-reload", sudo=True)
        ssh.run("systemctl enable --now ids", sudo=True)

    def _save_config(self, ssh: SSHSession, config: DeployConfig, elk_ip: str) -> None:
        python_code = (
            "from db.database import Database; "
            "db = Database('db/ids.db'); "
            "db.save_deployment_config("
            f"{json.dumps(config.aws_region)}, "
            f"{json.dumps(elk_ip)}, "
            f"{json.dumps(config.elastic_password)}, "
            f"{json.dumps(config.pi_host)}, "
            f"{json.dumps(config.pi_user)}, "
            f"{json.dumps(config.pi_password)}, "
            f"{json.dumps(config.sudo_password)}, "
            f"{json.dumps(config.remote_dir)}, "
            f"{json.dumps(config.mirror_interface)}"
            ")"
        )
        ssh.run(f"cd '{config.remote_dir}' && python3 -c {json.dumps(python_code)}", sudo=True)


if __name__ == "__main__":
    app = OrchestratorGUI()
    app.mainloop()
