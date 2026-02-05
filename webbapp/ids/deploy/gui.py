"""Tkinter GUI for IDS deployment."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from .config import DeployConfig
from .orchestrator import DeploymentOrchestrator


class OrchestratorGUI(tk.Tk):
    """GUI for IDS deployment orchestration."""
    
    def __init__(self) -> None:
        super().__init__()
        self.title("IDS2 - Orchestrator")
        self.geometry("960x720")
        self.resizable(True, True)
        
        self.log_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.orchestrator = DeploymentOrchestrator(self.log)
        
        self._build_ui()
        self.after(200, self._process_log_queue)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        main = ttk.Frame(self, padding=12)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)

        # Credentials
        creds = ttk.LabelFrame(main, text="Configuration", padding=10)
        creds.grid(row=0, column=0, sticky="ew")
        for idx in range(2):
            creds.columnconfigure(idx, weight=1)

        self.aws_region = self._add_entry(creds, "AWS Region", 0, "eu-west-1")
        self.elastic_password = self._add_entry(creds, "Elastic Password (required)", 1, "", show=True)
        self.pi_host = self._add_entry(creds, "Pi Host/IP", 2, "192.168.178.66")
        self.pi_user = self._add_entry(creds, "Pi User", 3, "pi")
        self.pi_password = self._add_entry(creds, "Pi Password", 4, "pi", show=True)
        self.sudo_password = self._add_entry(creds, "Sudo Password", 5, "pi", show=True)
        self.remote_dir = self._add_entry(creds, "Remote Directory", 6, "/opt/ids2")
        self.mirror_interface = self._add_entry(creds, "Mirror Interface (network port for traffic capture)", 7, "eth0")

        self.reset_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(creds, text="Reset complete", variable=self.reset_var).grid(row=8, column=0, columnspan=2, sticky="w", pady=(8, 0))

        self.install_docker_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(creds, text="Install Docker", variable=self.install_docker_var).grid(row=9, column=0, columnspan=2, sticky="w")

        self.remove_docker_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(creds, text="Remove Docker", variable=self.remove_docker_var).grid(row=10, column=0, columnspan=2, sticky="w")

        # Actions
        action_frame = ttk.Frame(main)
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
        self.progress = ttk.Progressbar(main, mode="determinate")
        self.progress.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        # Logs
        log_frame = ttk.LabelFrame(main, text="Logs", padding=10)
        log_frame.grid(row=3, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main.rowconfigure(3, weight=1)

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
        return DeployConfig(
            elastic_password=self.elastic_password.get().strip(),
            aws_region=self.aws_region.get().strip() or "eu-west-1",
            pi_host=self.pi_host.get().strip() or "192.168.178.66",
            pi_user=self.pi_user.get().strip() or "pi",
            pi_password=self.pi_password.get().strip() or "pi",
            sudo_password=self.sudo_password.get().strip() or "pi",
            remote_dir=self.remote_dir.get().strip() or "/opt/ids2",
            mirror_interface=self.mirror_interface.get().strip() or "eth0",
            reset_first=self.reset_var.get() if reset_override is None else reset_override,
            install_docker=self.install_docker_var.get(),
            remove_docker=self.remove_docker_var.get(),
        )

    def start_deploy(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        config = self._collect_config()
        if not config.elastic_password:
            messagebox.showerror("Error", "Elastic Password is required")
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


def main():
    app = OrchestratorGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
