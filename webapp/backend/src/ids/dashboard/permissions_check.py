#!/usr/bin/env python3
"""
IDS Dashboard permission pre-flight checker.

Why this exists
---------------
The dashboard includes features that rely on privileged operations:
- `systemctl start ...` (first-run workflow)
- `sudo ip link set <iface> promisc on` (mirror interface)
- reading Suricata logs (typically root-owned)
- optional access to Docker socket and GPIO

Those features only work if the dashboard process (and its service user) has the
right permissions. This module provides a safe, standalone check you can run
before starting the dashboard.

Safety
------
- Uses `systemctl --dry-run` when checking start permissions (no side effects).
- Does NOT toggle promiscuous mode on a real interface; it probes sudo/netadmin
  permission using a fake interface name.
"""

from __future__ import annotations

import argparse
import json
import os
import pwd
import shlex
import shutil
import subprocess
import textwrap
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class CommandResult:
    argv: list[str]
    ok: bool
    returncode: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    timeout: bool = False


@dataclass
class CheckResult:
    name: str
    ok: bool
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    commands: list[CommandResult] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)


@dataclass
class Report:
    generated_at: str
    hostname: str
    user: str
    uid: int
    euid: int
    groups: list[str]
    checks: list[CheckResult]

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)


def _run(argv: list[str], *, timeout_s: float = 8.0) -> CommandResult:
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_s,
        )
        return CommandResult(
            argv=argv,
            ok=(proc.returncode == 0),
            returncode=proc.returncode,
            stdout=(proc.stdout or "").strip(),
            stderr=(proc.stderr or "").strip(),
        )
    except subprocess.TimeoutExpired:
        return CommandResult(argv=argv, ok=False, timeout=True)
    except FileNotFoundError as exc:
        return CommandResult(argv=argv, ok=False, returncode=None, stderr=str(exc))


def _format_cmd(argv: list[str]) -> str:
    return " ".join(shlex.quote(x) for x in argv)


def _get_groups(user: str) -> list[str]:
    try:
        import grp

        gids = set(os.getgroups())
        # primary group
        try:
            gids.add(pwd.getpwnam(user).pw_gid)
        except Exception:
            pass
        names = []
        for gid in sorted(gids):
            try:
                names.append(grp.getgrgid(gid).gr_name)
            except KeyError:
                continue
        return names
    except Exception:
        return []


def check_sudo_nopasswd() -> CheckResult:
    if shutil.which("sudo") is None:
        return CheckResult(
            name="sudo",
            ok=False,
            summary="sudo not installed",
            hints=["Install sudo or run the dashboard/service with appropriate privileges."],
        )

    res = _run(["sudo", "-n", "true"], timeout_s=3.0)
    ok = res.ok
    hints: list[str] = []
    if not ok:
        hints.append("sudo is present but requires a password (NOPASSWD missing).")
        hints.append("If the dashboard must run privileged commands, configure sudo NOPASSWD for the service user.")
        hints.append("Example (edit with visudo): '<user> ALL=(root) NOPASSWD: /usr/sbin/ip, /bin/systemctl'")
        hints.append("Security note: keep the allowed command list narrow.")
    return CheckResult(
        name="sudo_nopasswd",
        ok=ok,
        summary="sudo -n works (NOPASSWD)" if ok else "sudo -n requires password",
        commands=[res],
        hints=hints,
    )


def check_systemctl_services(services: list[str]) -> CheckResult:
    if shutil.which("systemctl") is None:
        return CheckResult(
            name="systemd_services",
            ok=False,
            summary="systemctl not found (systemd not available)",
        )

    commands: list[CommandResult] = []
    missing_units: set[str] = set()
    permission_denied: set[str] = set()
    can_start_dry_run: set[str] = set()

    for service in services:
        res = _run(["systemctl", "is-active", service], timeout_s=4.0)
        commands.append(res)
        combined = f"{res.stdout or ''}\n{res.stderr or ''}".lower()
        if "could not be found" in combined or "not-found" in combined:
            missing_units.add(service)

    for service in services:
        res = _run(
            ["systemctl", "--no-ask-password", "--dry-run", "start", service],
            timeout_s=6.0,
        )
        commands.append(res)
        combined = f"{res.stdout or ''}\n{res.stderr or ''}".lower()
        if res.ok:
            can_start_dry_run.add(service)
            continue
        if "could not be found" in combined or "not-found" in combined:
            missing_units.add(service)
            continue
        if any(
            tok in combined
            for tok in (
                "access denied",
                "authentication is required",
                "not authorized",
                "polkit",
            )
        ):
            permission_denied.add(service)

    ok = len(permission_denied) == 0
    hints: list[str] = []
    if permission_denied:
        hints.append(
            "Dashboard can read service status, but starting services needs privileges (root/polkit/sudo)."
        )
        hints.append(
            "If you need /api/setup/first-run to start services, run the dashboard with sufficient permissions "
            "or use a restricted privileged helper."
        )
    if missing_units:
        hints.append(f"Missing systemd units: {', '.join(sorted(missing_units))}")

    return CheckResult(
        name="systemd_services",
        ok=ok,
        summary=(
            "systemctl start (dry-run) authorized"
            if ok
            else f"no permission to start: {', '.join(sorted(permission_denied))}"
        ),
        details={
            "services": services,
            "missing_units": sorted(missing_units),
            "permission_denied": sorted(permission_denied),
            "can_start_dry_run": sorted(can_start_dry_run),
        },
        commands=commands,
        hints=hints,
    )


def check_promiscuous_permissions(interface: str) -> CheckResult:
    if shutil.which("ip") is None:
        return CheckResult(
            name="net_promisc",
            ok=False,
            summary="'ip' command not found",
            hints=["Install iproute2 (package usually named 'iproute2')."],
        )

    commands: list[CommandResult] = []
    show = _run(["ip", "link", "show", interface], timeout_s=3.0)
    commands.append(show)
    if show.returncode != 0:
        return CheckResult(
            name="net_promisc",
            ok=False,
            summary=f"interface '{interface}' not found/readable",
            commands=commands,
        )

    already_promisc = "PROMISC" in (show.stdout or "")

    sudo_available = shutil.which("sudo") is not None
    sudo_probe_ok = False
    probe: CommandResult | None = None
    if sudo_available:
        # No side effect: fake interface. With permission, error becomes "Cannot find device".
        probe = _run(
            ["sudo", "-n", "ip", "link", "set", "__ids2_permcheck0", "promisc", "on"],
            timeout_s=3.0,
        )
        commands.append(probe)
        probe_text = f"{probe.stdout or ''}\n{probe.stderr or ''}".lower()
        sudo_probe_ok = probe.ok or ("cannot find device" in probe_text) or ("does not exist" in probe_text)

    ok = already_promisc or sudo_probe_ok
    hints: list[str] = []
    if not already_promisc:
        hints.append("Dashboard tries: sudo ip link set <iface> promisc on")
    if not sudo_probe_ok:
        hints.append(
            "If promisc enable is required, configure sudo NOPASSWD for /usr/sbin/ip or grant CAP_NET_ADMIN to the dashboard service."
        )

    return CheckResult(
        name="net_promisc",
        ok=ok,
        summary=(
            f"{interface} already PROMISC"
            if already_promisc
            else ("sudo can run ip link set" if sudo_probe_ok else "cannot run sudo ip link set (nopasswd missing)")
        ),
        details={
            "interface": interface,
            "already_promisc": already_promisc,
            "sudo_available": sudo_available,
            "sudo_probe_ok": sudo_probe_ok,
        },
        commands=commands,
        hints=hints,
    )


def check_suricata_log_access(log_path: str) -> CheckResult:
    path = Path(log_path)
    details: dict[str, Any] = {"path": str(path)}
    if not path.exists():
        return CheckResult(
            name="suricata_log",
            ok=False,
            summary=f"not found: {path}",
            details=details,
            hints=["Ensure Suricata writes eve.json and the path matches the dashboard config."],
        )

    st = path.stat()
    details.update(
        {
            "readable": os.access(path, os.R_OK),
            "mode": oct(st.st_mode & 0o777),
            "owner_uid": st.st_uid,
            "group_gid": st.st_gid,
            "size": st.st_size,
        }
    )
    ok = bool(details["readable"])
    hints: list[str] = []
    if not ok:
        hints.append("Dashboard needs read access to eve.json for alerts (/ws/alerts, /api/alerts/recent).")
        hints.append("Fix options: add dashboard user to the log group (often 'adm' or 'suricata') or adjust ACL/permissions.")

    try:
        with path.open("rb") as handle:
            handle.read(64)
        details["sample_read_ok"] = True
    except Exception as exc:
        details["sample_read_ok"] = False
        details["sample_read_error"] = str(exc)

    return CheckResult(
        name="suricata_log",
        ok=ok,
        summary="readable" if ok else "NOT readable",
        details=details,
        hints=hints,
    )


def check_docker_access() -> CheckResult:
    if shutil.which("docker") is None:
        return CheckResult(
            name="docker",
            ok=False,
            summary="docker CLI not installed",
            hints=["Install Docker (or use the deployment scripts that install Docker on the Pi)."],
        )

    commands: list[CommandResult] = []
    ps = _run(["docker", "ps"], timeout_s=6.0)
    commands.append(ps)
    compose = _run(["docker", "compose", "version"], timeout_s=6.0)
    commands.append(compose)

    ok = ps.ok
    hints: list[str] = []
    combined = f"{ps.stdout or ''}\n{ps.stderr or ''}".lower()
    if not ok:
        if "permission denied" in combined and ("docker.sock" in combined or "/var/run/docker.sock" in combined):
            hints.append("No permission to access Docker socket.")
            hints.append("Fix: sudo usermod -aG docker <user> (then log out/in), or run docker via sudo.")
        elif "cannot connect" in combined:
            hints.append("Docker daemon not running. Check: systemctl status docker")

    return CheckResult(
        name="docker",
        ok=ok,
        summary="docker ps works" if ok else "docker ps failed",
        commands=commands,
        hints=hints,
    )


def check_dashboard_data_dir(workdir: str | None) -> CheckResult:
    base = Path(workdir) if workdir else Path.cwd()
    data_dir = base / "data"
    probe = data_dir / ".permcheck"
    details = {"workdir": str(base), "data_dir": str(data_dir)}
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink(missing_ok=True)
        ok = True
    except Exception as exc:
        ok = False
        details["error"] = str(exc)

    hints: list[str] = []
    if not ok:
        hints.append("Dashboard needs write access to <WorkingDirectory>/data for the SQLite DB.")
        hints.append("Fix: ensure systemd unit WorkingDirectory is writable for the configured User=.")

    return CheckResult(
        name="dashboard_db_dir",
        ok=ok,
        summary="writable ./data" if ok else "cannot write ./data",
        details=details,
        hints=hints,
    )


def check_gpio_access(led_pin: int) -> CheckResult:
    try:
        from gpiozero import LED  # type: ignore
    except Exception as exc:
        # Not an error if hardware support isn't desired.
        return CheckResult(
            name="gpio",
            ok=True,
            summary="gpiozero not installed (skipped)",
            details={"error": str(exc)},
            hints=["Install gpiozero if you want LED alert support."],
        )

    try:
        led = LED(led_pin)
        led.off()
        led.close()
        return CheckResult(name="gpio", ok=True, summary=f"GPIO ok (pin {led_pin})")
    except Exception as exc:
        return CheckResult(
            name="gpio",
            ok=False,
            summary=f"GPIO failed (pin {led_pin})",
            details={"error": str(exc)},
            hints=[
                "Ensure the user has GPIO permissions (often group 'gpio') or run with appropriate privileges.",
                "On Raspberry Pi OS you may need: sudo usermod -aG gpio <user> (then re-login).",
            ],
        )


def build_report(args: argparse.Namespace) -> Report:
    user = pwd.getpwuid(os.getuid()).pw_name
    services = args.services or ["suricata", "vector", "ids-dashboard", "docker", "tailscaled"]
    checks = [
        check_sudo_nopasswd(),
        check_systemctl_services(services),
        check_promiscuous_permissions(args.interface),
        check_suricata_log_access(args.suricata_log),
        check_docker_access(),
        check_dashboard_data_dir(args.workdir),
        check_gpio_access(args.led_pin),
    ]
    return Report(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        hostname=os.uname().nodename,
        user=user,
        uid=os.getuid(),
        euid=os.geteuid(),
        groups=_get_groups(user),
        checks=checks,
    )


def _print_text(report: Report, *, show_commands: bool) -> None:
    print(
        f"IDS Dashboard permissions pre-flight ({report.hostname})\n"
        f"User: {report.user} (uid={report.uid}, euid={report.euid})\n"
        f"Groups: {', '.join(report.groups) or 'n/a'}\n"
        f"Time: {report.generated_at}"
    )
    print("=" * 88)

    for check in report.checks:
        status = "OK" if check.ok else "FAIL"
        print(f"[{status}] {check.name}: {check.summary}")
        if check.hints:
            for hint in check.hints:
                print(f"  - hint: {hint}")
        if show_commands and check.commands:
            for cmd in check.commands:
                cstatus = "OK" if cmd.ok else "FAIL"
                print(f"  - cmd [{cstatus}]: {_format_cmd(cmd.argv)}")
                if cmd.timeout:
                    print("    timeout")
                if cmd.returncode is not None:
                    print(f"    rc={cmd.returncode}")
                if cmd.stdout:
                    print("    stdout:")
                    print(textwrap.indent(cmd.stdout, "      "))
                if cmd.stderr:
                    print("    stderr:")
                    print(textwrap.indent(cmd.stderr, "      "))
        if check.details and (show_commands or not check.ok):
            print("  details:")
            for k, v in check.details.items():
                print(f"    {k}: {v}")
        print("")

    print("=" * 88)
    print("Overall:", "OK" if report.ok else "FAIL")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Check permissions required by ids.dashboard (systemctl, sudo ip, docker, logs, GPIO).",
    )
    p.add_argument(
        "--interface",
        default=os.getenv("MIRROR_INTERFACE", "eth0"),
        help="Mirror interface (default: MIRROR_INTERFACE or eth0)",
    )
    p.add_argument(
        "--suricata-log",
        default=os.getenv("SURICATA_EVE_LOG", "/var/log/suricata/eve.json"),
        help="Path to Suricata eve.json (default: /var/log/suricata/eve.json)",
    )
    p.add_argument(
        "--led-pin",
        type=int,
        default=int(os.getenv("LED_PIN", "17")),
        help="GPIO LED pin (default: LED_PIN or 17)",
    )
    p.add_argument(
        "--workdir",
        default=None,
        help="Workdir to test (defaults to cwd). Useful to mimic systemd WorkingDirectory.",
    )
    p.add_argument(
        "--service",
        dest="services",
        action="append",
        default=[],
        help="Add a systemd service to check (repeatable).",
    )
    p.add_argument("--json", dest="as_json", action="store_true", help="Output JSON")
    p.add_argument("--show-commands", action="store_true", help="Include commands + stdout/stderr in text output")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(args)
    if args.as_json:
        payload = asdict(report)
        payload["ok"] = report.ok
        print(json.dumps(payload, indent=2))
    else:
        _print_text(report, show_commands=args.show_commands)
    return 0 if report.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

