"""Tkinter GUI orchestrator for AWS + Pi2 deployment."""

from __future__ import annotations

import io
import json
import os
import posixpath
import queue
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk
import uuid

import paramiko

from orchestrator import SuricataMaster


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
        self.remote_dir = self._add_entry(creds, "Remote Dir", 6, "/opt/ids-dashboard")
        self.mirror_interface = self._add_entry(creds, "Mirror Interface", 7, "eth0")

        self.reset_var = tk.BooleanVar(value=False)
        reset_check = ttk.Checkbutton(
            creds,
            text="Reset complet (suppression services, docker, scripts)",
            variable=self.reset_var,
        )
        reset_check.grid(row=8, column=0, columnspan=2, sticky="w", pady=(8, 0))

        action_frame = ttk.Frame(main)
        action_frame.grid(row=1, column=0, sticky="ew", pady=10)
        action_frame.columnconfigure(1, weight=1)

        self.deploy_button = ttk.Button(action_frame, text="Déployer", command=self.start_deploy)
        self.deploy_button.grid(row=0, column=0, padx=(0, 10))

        self.reset_button = ttk.Button(action_frame, text="Reset uniquement", command=self.start_reset_only)
        self.reset_button.grid(row=0, column=1, sticky="w")

        self.progress_label = ttk.Label(action_frame, text="Idle")
        self.progress_label.grid(row=0, column=2, sticky="e")

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

    def _start_worker(self, target) -> None:
        self.deploy_button.config(state="disabled")
        self.reset_button.config(state="disabled")
        self.progress["value"] = 0
        self.log_text.delete("1.0", "end")
        self.worker = threading.Thread(target=target, daemon=True)
        self.worker.start()

    def _finish_worker(self) -> None:
        self.deploy_button.config(state="normal")
        self.reset_button.config(state="normal")

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

    def _run_deploy(self, config: DeployConfig) -> None:
        try:
            step = 0
            total_steps = 7 + (1 if config.reset_first else 0)

            def advance(label: str) -> None:
                nonlocal step
                step += 1
                self.set_progress(step / total_steps * 100, label)

            with self._ssh_session(config) as ssh:
                advance("Connexion Pi2")
                if config.reset_first:
                    self._reset_remote(ssh, config)
                    advance("Reset complet")

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
        ssh.run("systemctl disable --now webapp2 || true", sudo=True, check=False)
        ssh.run("systemctl disable --now ids || true", sudo=True, check=False)
        ssh.run("systemctl disable --now suricata || true", sudo=True, check=False)
        ssh.run("rm -f /etc/systemd/system/webapp2.service /etc/systemd/system/ids.service", sudo=True, check=False)
        ssh.run("systemctl daemon-reload", sudo=True, check=False)
        ssh.run(f"rm -rf '{config.remote_dir}'", sudo=True, check=False)
        ssh.run("ufw --force reset", sudo=True, check=False)
        ssh.run("apt purge -y docker.io docker-compose containerd runc || true", sudo=True, check=False)
        ssh.run("apt purge -y suricata || true", sudo=True, check=False)
        ssh.run("rm -rf /etc/suricata /var/log/suricata || true", sudo=True, check=False)
        ssh.run("pip3 uninstall -y boto3 elasticsearch requests || true", sudo=True, check=False)
        self.log("✅ Reset complet terminé.")

    def _install_probe(self, ssh: SSHSession, config: DeployConfig) -> None:
        local_script = Path(__file__).parent / "install_pi_probe.sh"
        script_content = local_script.read_text(encoding="utf-8")
        ssh.write_remote_file("/tmp/install_pi_probe.sh", script_content, sudo=False)
        ssh.run("chmod +x /tmp/install_pi_probe.sh", sudo=True)
        ssh.run(f"MIRROR_INTERFACE={config.mirror_interface} bash /tmp/install_pi_probe.sh", sudo=True)

    def _deploy_webapp2(self, ssh: SSHSession, config: DeployConfig) -> None:
        local_dir = Path(__file__).parent
        ssh.run(f"mkdir -p '{config.remote_dir}'", sudo=True)
        ssh.run(f"chown -R {config.pi_user}:{config.pi_user} '{config.remote_dir}'", sudo=True)
        ssh.put_dir(local_dir, config.remote_dir)
        ssh.run(f"chmod +x '{config.remote_dir}/start.sh'", sudo=True)
        ssh.run("apt update && apt install -y python3-venv python3-pip", sudo=True)

        service = (
            "[Unit]\n"
            "Description=IDS WebApp2\n"
            "After=network.target\n\n"
            "[Service]\n"
            f"WorkingDirectory={config.remote_dir}\n"
            f"ExecStart=/bin/bash -lc '{config.remote_dir}/start.sh'\n"
            "Environment=RUN_MODE=prod\n"
            "Restart=always\n"
            f"User={config.pi_user}\n\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n"
        )
        ssh.write_remote_file("/etc/systemd/system/webapp2.service", service, sudo=True)
        ssh.run("systemctl daemon-reload", sudo=True)
        ssh.run("systemctl enable --now webapp2", sudo=True)

    def _install_streamer_service(self, ssh: SSHSession, config: DeployConfig, elk_ip: str) -> None:
        service_path = posixpath.join(config.remote_dir, "orchestrator.py")
        service = SuricataMaster.build_systemd_service(service_path, elk_ip, config.elastic_password)
        ssh.write_remote_file("/etc/systemd/system/ids.service", service, sudo=True)
        ssh.run("systemctl daemon-reload", sudo=True)
        ssh.run("systemctl enable --now ids", sudo=True)

    def _save_config(self, ssh: SSHSession, config: DeployConfig, elk_ip: str) -> None:
        script = (
            "from db.database import Database\n"
            "db = Database('db/ids.db')\n"
            "db.save_deployment_config(\n"
            f"    {json.dumps(config.aws_region)},\n"
            f"    {json.dumps(elk_ip)},\n"
            f"    {json.dumps(config.elastic_password)},\n"
            f"    {json.dumps(config.pi_host)},\n"
            f"    {json.dumps(config.pi_user)},\n"
            f"    {json.dumps(config.pi_password)},\n"
            f"    {json.dumps(config.sudo_password)},\n"
            f"    {json.dumps(config.remote_dir)},\n"
            f"    {json.dumps(config.mirror_interface)},\n"
            ")\n"
        )
        ssh.run(
            f"cd '{config.remote_dir}' && python3 - <<'PY'\n{script}PY",
            sudo=True,
        )


if __name__ == "__main__":
    app = OrchestratorGUI()
    app.mainloop()
