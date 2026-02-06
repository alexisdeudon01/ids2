"""Tkinter GUI for IDS deployment."""

from __future__ import annotations

import json
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .config import DeployConfig
from .aws_deployer import AWSDeployer
from .orchestrator import DeploymentHalted, DeploymentOrchestrator


class OrchestratorGUI(tk.Tk):
    """GUI for IDS deployment orchestration."""
    
    def __init__(self) -> None:
        super().__init__()
        self.title("IDS2 - Orchestrator")
        self.geometry("960x720")
        self.resizable(True, True)
        
        self.log_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.orchestrator = DeploymentOrchestrator(self.log, self._prompt_cost_action)
        self.config_defaults = self._load_config_defaults()
        
        self._build_ui()
        self.after(200, self._process_log_queue)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        main_frame = ttk.Frame(self, padding=12)
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.columnconfigure(0, weight=1)

        # Credentials
        creds = ttk.LabelFrame(main_frame, text="Configuration", padding=10)
        creds.grid(row=0, column=0, sticky="ew")
        for idx in range(2):
            creds.columnconfigure(idx, weight=1)

        self.aws_region = self._add_entry(creds, "AWS Region", 0, self._config_default("aws_region", "eu-west-1"))
        self.aws_access_key_id = self._add_entry(
            creds,
            "AWS Access Key ID (optional)",
            1,
            self._config_default("aws_access_key_id", os.getenv("AWS_ACCESS_KEY_ID", "")),
        )
        self.aws_secret_access_key = self._add_entry(
            creds,
            "AWS Secret Access Key (optional)",
            2,
            self._config_default("aws_secret_access_key", os.getenv("AWS_SECRET_ACCESS_KEY", "")),
            show=True,
        )
        self.aws_ami_id = self._add_entry(
            creds,
            "AWS AMI ID (optional)",
            3,
            self._config_default("aws_ami_id", ""),
        )
        self.elastic_password = self._add_entry(
            creds,
            "Elastic Password (required)",
            4,
            self._config_default("elastic_password", ""),
            show=True,
        )
        self.pi_host = self._add_entry(creds, "Pi Hostname", 5, self._config_default("pi_host", "sinik"))
        self.pi_ip = self._add_entry(creds, "Pi IP (optional)", 6, self._config_default("pi_ip", "192.168.178.66"))
        self.pi_user = self._add_entry(creds, "Pi User", 7, self._config_default("pi_user", "pi"))
        self.pi_password = self._add_entry(creds, "Pi Password", 8, self._config_default("pi_password", "pi"), show=True)
        self.ssh_key_path = self._add_entry(
            creds,
            "SSH Key Path (optional)",
            9,
            self._config_default("ssh_key_path", self._default_ssh_key_path()),
        )
        self.sudo_password = self._add_entry(
            creds, "Sudo Password", 10, self._config_default("sudo_password", "pi"), show=True
        )
        self.remote_dir = self._add_entry(creds, "Remote Directory", 11, self._config_default("remote_dir", "/opt/ids2"))
        self.mirror_interface = self._add_entry(
            creds,
            "Mirror Interface (network port for traffic capture)",
            12,
            self._config_default("mirror_interface", "eth0"),
        )

        self.instances_count_var = tk.StringVar(value="0")
        ttk.Label(creds, text="ELK Instances (all regions)").grid(row=13, column=0, sticky="w", pady=4)
        ttk.Label(creds, textvariable=self.instances_count_var).grid(row=13, column=1, sticky="w", pady=4)

        self.reset_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(creds, text="Reset complete", variable=self.reset_var).grid(row=14, column=0, columnspan=2, sticky="w", pady=(8, 0))

        self.install_docker_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(creds, text="Install Docker", variable=self.install_docker_var).grid(row=15, column=0, columnspan=2, sticky="w")

        self.remove_docker_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(creds, text="Remove Docker", variable=self.remove_docker_var).grid(row=16, column=0, columnspan=2, sticky="w")

        # Actions
        action_frame = ttk.Frame(main_frame)
        action_frame.grid(row=1, column=0, sticky="ew", pady=10)
        action_frame.columnconfigure(4, weight=1)

        self.deploy_button = ttk.Button(action_frame, text="Deploy", command=self.start_deploy)
        self.deploy_button.grid(row=0, column=0, padx=(0, 10))

        self.reset_button = ttk.Button(action_frame, text="Reset Only", command=self.start_reset_only)
        self.reset_button.grid(row=0, column=1, padx=(0, 10))

        self.install_docker_button = ttk.Button(action_frame, text="Install Docker", command=self.start_install_docker_only)
        self.install_docker_button.grid(row=0, column=2, padx=(0, 10))

        self.remove_docker_button = ttk.Button(action_frame, text="Remove Docker", command=self.start_remove_docker_only)
        self.remove_docker_button.grid(row=0, column=3)

        self.progress_label = ttk.Label(action_frame, text="Idle")
        self.progress_label.grid(row=0, column=4, sticky="e")

        # Progress
        self.progress = ttk.Progressbar(main_frame, mode="determinate")
        self.progress.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        # Logs
        log_frame = ttk.LabelFrame(main_frame, text="Logs", padding=10)
        log_frame.grid(row=3, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)

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
        pi_host = self.pi_host.get().strip() or self.pi_ip.get().strip() or "sinik"
        return DeployConfig(
            elastic_password=self.elastic_password.get().strip(),
            aws_region=self.aws_region.get().strip() or "eu-west-1",
            aws_access_key_id=self.aws_access_key_id.get().strip(),
            aws_secret_access_key=self.aws_secret_access_key.get().strip(),
            aws_ami_id=self.aws_ami_id.get().strip(),
            ssh_key_path=self.ssh_key_path.get().strip(),
            pi_host=pi_host,
            pi_ip=self.pi_ip.get().strip() or "192.168.178.66",
            pi_user=self.pi_user.get().strip() or "pi",
            pi_password=self.pi_password.get().strip() or "pi",
            sudo_password=self.sudo_password.get().strip() or "pi",
            remote_dir=self.remote_dir.get().strip() or "/opt/ids2",
            mirror_interface=self.mirror_interface.get().strip() or "eth0",
            reset_first=self.reset_var.get() if reset_override is None else reset_override,
            install_docker=self.install_docker_var.get(),
            remove_docker=self.remove_docker_var.get(),
        )

    def _default_ssh_key_path(self) -> str:
        candidates = [
            Path("/home/tor/.ssh/pi_key"),
            Path("~/.ssh/id_ed25519").expanduser(),
            Path("~/.ssh/id_rsa").expanduser(),
        ]
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
        return ""

    def _load_config_defaults(self) -> dict[str, str]:
        config_path = Path(__file__).resolve().parents[3] / "config.json"
        if not config_path.is_file():
            return {}
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _config_default(self, key: str, fallback: str) -> str:
        value = self.config_defaults.get(key, "")
        return value if value else fallback

    def start_deploy(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        config = self._collect_config()
        if not config.elastic_password:
            messagebox.showerror("Error", "Elastic Password is required")
            return
        if not self._preflight_check_instances(config):
            return
        self._start_worker(lambda: self._run_deploy(config))

    def start_reset_only(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        config = self._collect_config(reset_override=True)
        self._start_worker(lambda: self._run_reset_only(config))

    def start_install_docker_only(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        config = self._collect_config()
        self._start_worker(lambda: self._run_install_docker(config))

    def start_remove_docker_only(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        config = self._collect_config()
        self._start_worker(lambda: self._run_remove_docker(config))

    def _start_worker(self, target) -> None:
        for btn in [self.deploy_button, self.reset_button, self.install_docker_button, self.remove_docker_button]:
            btn.config(state="disabled")
        self.progress["value"] = 0
        self.log_text.delete("1.0", "end")
        self.worker = threading.Thread(target=target, daemon=True)
        self.worker.start()

    def _finish_worker(self) -> None:
        for btn in [self.deploy_button, self.reset_button, self.install_docker_button, self.remove_docker_button]:
            btn.config(state="normal")

    def _run_deploy(self, config: DeployConfig) -> None:
        try:
            elk_ip = self.orchestrator.full_deploy(config, self.set_progress)
            self.set_progress(100, "Deployment complete")
            self.log(f"✅ Kibana Dashboard: http://{elk_ip}:5601")
        except DeploymentHalted as exc:
            self.log(f"ℹ️ Deployment stopped: {exc}")
            self.set_progress(0, "Stopped")
        except Exception as exc:
            self.log(f"❌ Deployment error: {exc}")
            self.set_progress(0, "Error")
        finally:
            self._finish_worker()

    def _run_reset_only(self, config: DeployConfig) -> None:
        try:
            self.orchestrator.reset_only(config, self.set_progress)
        except Exception as exc:
            self.log(f"❌ Reset error: {exc}")
            self.set_progress(0, "Error")
        finally:
            self._finish_worker()

    def _run_install_docker(self, config: DeployConfig) -> None:
        try:
            self.orchestrator.install_docker_only(config, self.set_progress)
        except Exception as exc:
            self.log(f"❌ Docker error: {exc}")
            self.set_progress(0, "Error")
        finally:
            self._finish_worker()

    def _run_remove_docker(self, config: DeployConfig) -> None:
        try:
            self.orchestrator.remove_docker_only(config, self.set_progress)
        except Exception as exc:
            self.log(f"❌ Docker removal error: {exc}")
            self.set_progress(0, "Error")
        finally:
            self._finish_worker()

    def _preflight_check_instances(self, config: DeployConfig) -> bool:
        """Ensure we have at most one ELK instance across regions."""
        try:
            aws = AWSDeployer(
                config.aws_region,
                config.elastic_password,
                self.log,
                aws_access_key_id=config.aws_access_key_id,
                aws_secret_access_key=config.aws_secret_access_key,
                ami_id=config.aws_ami_id,
            )
            instances = aws.list_tagged_instances_all_regions()
            self.instances_count_var.set(str(len(instances)))
            if len(instances) <= 1:
                return True

            details = "\n".join(
                f"- {item.get('region')} {item.get('id')} ({item.get('state')})"
                for item in instances
            )
            confirm = messagebox.askyesno(
                "Instances multiples",
                f"{len(instances)} instances ELK trouvées:\n{details}\n\n"
                "Supprimer toutes les instances en trop ?",
            )
            if confirm:
                keep = aws.select_instance_to_keep(instances)
                keep_id = keep.get("id") if keep else None
                aws.terminate_instances_across_regions(instances, keep_id=keep_id)
                instances = aws.list_tagged_instances_all_regions()
                self.instances_count_var.set(str(len(instances)))
            return True
        except Exception as exc:
            self.log(f"⚠️ Instance check failed: {exc}")
            return True

    def _prompt_cost_action(self, cost_info: dict) -> str:
        """Ask user what to do with current AWS cost."""
        result = {"action": "continue"}
        event = threading.Event()

        def _show():
            dialog = tk.Toplevel(self)
            dialog.title("AWS Cost Confirmation")
            dialog.geometry("520x260")
            dialog.resizable(False, False)
            dialog.grab_set()

            instance_id = cost_info.get("instance_id", "")
            instance_type = cost_info.get("instance_type", "")
            region = cost_info.get("region", "")
            ec2_hour = cost_info.get("ec2_hourly_usd", 0)
            ec2_month = cost_info.get("ec2_monthly_usd", 0)
            elastic_hour = cost_info.get("elastic_hourly_usd", 0)
            elastic_month = cost_info.get("elastic_monthly_usd", 0)
            total_hour = cost_info.get("total_hourly_usd", 0)
            total_month = cost_info.get("total_monthly_usd", 0)

            info = (
                f"Instance: {instance_id} ({instance_type})\n"
                f"Region: {region}\n\n"
                f"EC2: ${ec2_hour:.4f}/h (~${ec2_month:.2f}/mois)\n"
                f"Elastic (Docker): ${elastic_hour:.4f}/h (~${elastic_month:.2f}/mois)\n"
                f"Total: ${total_hour:.4f}/h (~${total_month:.2f}/mois)"
            )

            ttk.Label(dialog, text="Coût estimé (On-Demand)", font=("Arial", 12, "bold")).pack(pady=(10, 4))
            ttk.Label(dialog, text=info, justify="left").pack(padx=12, pady=6)

            btn_frame = ttk.Frame(dialog)
            btn_frame.pack(pady=12)

            def _set_action(value: str) -> None:
                result["action"] = value
                dialog.destroy()
                event.set()

            ttk.Button(btn_frame, text="Continue", command=lambda: _set_action("continue")).grid(row=0, column=0, padx=6)
            ttk.Button(
                btn_frame,
                text="Stop & Delete Elastic",
                command=lambda: _set_action("stop_elastic"),
            ).grid(row=0, column=1, padx=6)
            ttk.Button(
                btn_frame,
                text="Stop & Delete Instance",
                command=lambda: _set_action("stop_instance"),
            ).grid(row=0, column=2, padx=6)

        self.after(0, _show)
        event.wait()
        return result["action"]


def main():
    app = OrchestratorGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
