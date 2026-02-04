#!/usr/bin/env python3
"""
Tailscale Network Verification Script.

Utilise la librairie Python `tailscale` pour vérifier la configuration
et la connectivité du réseau Tailscale.
"""

from __future__ import annotations

import asyncio
import getpass
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ajouter le chemin src au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from tailscale import Tailscale

    TAILSCALE_LIB_AVAILABLE = True
except ImportError:
    TAILSCALE_LIB_AVAILABLE = False
    print("⚠ La librairie 'tailscale' n'est pas installée.")
    print("  Installez-la avec: pip install tailscale")


# Couleurs ANSI
class Colors:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    CYAN = "\033[0;36m"
    MAGENTA = "\033[0;35m"
    NC = "\033[0m"
    BOLD = "\033[1m"


def print_header(title: str) -> None:
    print(f"\n{Colors.CYAN}{'═' * 60}{Colors.NC}")
    print(f"{Colors.BOLD}{Colors.BLUE}  {title}{Colors.NC}")
    print(f"{Colors.CYAN}{'═' * 60}{Colors.NC}\n")


def print_success(msg: str) -> None:
    print(f"{Colors.GREEN}✓{Colors.NC} {msg}")


def print_error(msg: str) -> None:
    print(f"{Colors.RED}✗{Colors.NC} {msg}")


def print_warn(msg: str) -> None:
    print(f"{Colors.YELLOW}⚠{Colors.NC} {msg}")


def print_info(msg: str) -> None:
    print(f"{Colors.BLUE}ℹ{Colors.NC} {msg}")


@dataclass
class DeviceInfo:
    """Informations sur un appareil Tailscale."""

    id: str
    name: str
    hostname: str
    addresses: List[str]
    os: str
    authorized: bool
    is_external: bool
    last_seen: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)

    @property
    def ipv4(self) -> str:
        """Retourne l'adresse IPv4 principale."""
        for addr in self.addresses:
            if "." in addr and not addr.startswith("fd7a:"):
                return addr
        return self.addresses[0] if self.addresses else ""

    @property
    def is_online(self) -> bool:
        """Vérifie si l'appareil est probablement en ligne."""
        if self.last_seen is None:
            return True  # Pas d'info = on suppose en ligne
        delta = datetime.now(self.last_seen.tzinfo) - self.last_seen
        return delta.total_seconds() < 300  # Moins de 5 minutes


@dataclass
class TailnetInfo:
    """Informations sur le tailnet."""

    name: str
    devices: List[DeviceInfo] = field(default_factory=list)
    dns_suffix: str = ""


async def get_tailnet_info(tailnet: str, api_key: str) -> TailnetInfo:
    """
    Récupère les informations du tailnet via l'API Tailscale.

    Args:
        tailnet: Nom du tailnet (ex: "example.com" ou "user@gmail.com")
        api_key: Clé API Tailscale (tskey-api-...)

    Returns:
        TailnetInfo avec la liste des appareils
    """
    info = TailnetInfo(name=tailnet)

    async with Tailscale(tailnet=tailnet, api_key=api_key) as client:
        # Récupérer les appareils
        devices_response = await client.devices()

        for device_id, device in devices_response.devices.items():
            dev_info = DeviceInfo(
                id=device_id,
                name=device.name or "Unknown",
                hostname=device.hostname or "",
                addresses=device.addresses or [],
                os=device.os or "Unknown",
                authorized=device.authorized or False,
                is_external=device.is_external or False,
                last_seen=device.last_seen,
                tags=device.tags or [],
            )
            info.devices.append(dev_info)

    return info


def ping_device(ip: str, count: int = 3) -> tuple[bool, float]:
    """
    Ping un appareil via Tailscale CLI.

    Returns:
        (success, average_latency_ms)
    """
    try:
        result = subprocess.run(
            ["tailscale", "ping", "-c", str(count), ip],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return False, 0.0

        # Parser la latence
        import re

        latencies = re.findall(r"in (\d+(?:\.\d+)?)\s*ms", result.stdout)
        if latencies:
            avg = sum(float(l) for l in latencies) / len(latencies)
            return True, avg

        return True, 0.0
    except Exception:
        return False, 0.0


def check_local_tailscale() -> dict:
    """Vérifie l'installation locale de Tailscale."""
    info = {
        "installed": False,
        "version": "",
        "running": False,
        "connected": False,
        "self_ip": "",
    }

    # Version
    try:
        result = subprocess.run(
            ["tailscale", "version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            info["installed"] = True
            info["version"] = result.stdout.strip().split("\n")[0]
    except Exception:
        return info

    # Service
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "tailscaled"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        info["running"] = result.returncode == 0
    except Exception:
        pass

    # IP locale
    try:
        result = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            info["self_ip"] = result.stdout.strip()
            info["connected"] = True
    except Exception:
        pass

    return info


async def run_verification(tailnet: str, api_key: str, target_ip: Optional[str] = None) -> int:
    """
    Exécute la vérification complète du tailnet.

    Args:
        tailnet: Nom du tailnet
        api_key: Clé API Tailscale
        target_ip: IP optionnelle à tester spécifiquement (ex: Raspberry Pi)

    Returns:
        Code de sortie (0 = succès)
    """
    print(f"\n{Colors.MAGENTA}{'=' * 60}{Colors.NC}")
    print(f"{Colors.BOLD}{Colors.MAGENTA}  TAILSCALE NETWORK VERIFICATION{Colors.NC}")
    print(f"{Colors.MAGENTA}{'=' * 60}{Colors.NC}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Utilisant la librairie Python 'tailscale'")

    # Vérification locale
    print_header("Vérification Locale")
    local = check_local_tailscale()

    if local["installed"]:
        print_success(f"Tailscale installé (version {local['version']})")
    else:
        print_error("Tailscale n'est pas installé localement")
        print_info("Exécutez: ./scripts/tailscale_setup.sh install")

    if local["running"]:
        print_success("Service tailscaled actif")
    else:
        print_warn("Service tailscaled inactif")
        print_info("Exécutez: sudo systemctl start tailscaled")

    if local["connected"]:
        print_success(f"Connecté - IP locale: {local['self_ip']}")
    else:
        print_warn("Non connecté au tailnet localement")

    # Récupération des infos via API
    print_header(f"Tailnet: {tailnet}")

    try:
        info = await get_tailnet_info(tailnet, api_key)
        print_success(f"Connexion API réussie")
        print_info(f"Nombre d'appareils: {len(info.devices)}")
    except Exception as e:
        print_error(f"Erreur API: {e}")
        return 1

    # Liste des appareils
    print_header("Appareils sur le Tailnet")

    print(f"  {'Nom':<25} {'IP':<18} {'OS':<12} {'État':<12}")
    print(f"  {'-' * 25} {'-' * 18} {'-' * 12} {'-' * 12}")

    raspberry_pi = None

    for device in info.devices:
        ip = device.ipv4

        # Détecter le Raspberry Pi
        if target_ip and ip == target_ip:
            raspberry_pi = device
        elif "raspberry" in device.name.lower() or "pi" in device.name.lower():
            if raspberry_pi is None:
                raspberry_pi = device

        # Statut
        if device.authorized:
            status_color = Colors.GREEN
            status = "Autorisé"
        else:
            status_color = Colors.RED
            status = "Non autorisé"

        # Marquer si c'est nous
        is_self = ip == local.get("self_ip", "")
        self_marker = f" {Colors.YELLOW}(vous){Colors.NC}" if is_self else ""

        name = device.name[:23] + ".." if len(device.name) > 25 else device.name

        print(
            f"  {name:<25} {ip:<18} {device.os:<12} {status_color}{status:<12}{Colors.NC}{self_marker}"
        )

    # Tests de connectivité
    print_header("Tests de Connectivité")

    if target_ip:
        test_ip = target_ip
        print_info(f"Test de l'IP cible spécifiée: {target_ip}")
    elif raspberry_pi:
        test_ip = raspberry_pi.ipv4
        print_info(f"Raspberry Pi détecté: {raspberry_pi.name} ({test_ip})")
    else:
        # Tester le premier appareil autre que nous
        other_devices = [d for d in info.devices if d.ipv4 != local.get("self_ip", "")]
        if other_devices:
            test_ip = other_devices[0].ipv4
            print_info(f"Test du premier appareil: {other_devices[0].name} ({test_ip})")
        else:
            print_warn("Aucun autre appareil à tester")
            test_ip = None

    if test_ip and local["connected"]:
        print_info(f"Ping Tailscale vers {test_ip}...")
        success, latency = ping_device(test_ip)

        if success:
            print_success(f"Ping OK (latence: {latency:.1f}ms)")
        else:
            print_error("Ping échoué")
            print_info("Vérifiez que l'appareil est en ligne et autorisé")

    # Valeurs de configuration
    print_header("Configuration pour GitHub Actions")

    print(f"{Colors.BOLD}Secrets à configurer:{Colors.NC}")
    print()
    print(f"  {Colors.CYAN}TAILSCALE_TAILNET{Colors.NC}={Colors.GREEN}{tailnet}{Colors.NC}")
    print(f"  {Colors.CYAN}TAILSCALE_API_KEY{Colors.NC}={Colors.GREEN}(votre clé API){Colors.NC}")

    if raspberry_pi:
        print(
            f"  {Colors.CYAN}RASPBERRY_PI_TAILSCALE_IP{Colors.NC}={Colors.GREEN}{raspberry_pi.ipv4}{Colors.NC}"
        )
    elif target_ip:
        print(
            f"  {Colors.CYAN}RASPBERRY_PI_TAILSCALE_IP{Colors.NC}={Colors.GREEN}{target_ip}{Colors.NC}"
        )
    else:
        print(
            f"  {Colors.CYAN}RASPBERRY_PI_TAILSCALE_IP{Colors.NC}={Colors.YELLOW}(à définir){Colors.NC}"
        )

    print()
    print(f"{Colors.BOLD}Liens utiles:{Colors.NC}")
    print(f"  • API Key: {Colors.BLUE}https://login.tailscale.com/admin/settings/keys{Colors.NC}")
    print(f"  • OAuth:   {Colors.BLUE}https://login.tailscale.com/admin/settings/oauth{Colors.NC}")
    print(f"  • Machines:{Colors.BLUE}https://login.tailscale.com/admin/machines{Colors.NC}")

    print()
    print_success("Vérification terminée!")

    return 0


def main() -> int:
    """Point d'entrée principal."""
    if not TAILSCALE_LIB_AVAILABLE:
        print_error("La librairie 'tailscale' est requise.")
        print_info("Installez-la avec: pip install tailscale")
        return 1

    # Récupérer les credentials
    tailnet = os.environ.get("TAILSCALE_TAILNET")
    api_key = os.environ.get("TAILSCALE_API_KEY")
    target_ip = os.environ.get("RASPBERRY_PI_TAILSCALE_IP")

    # Mode interactif si pas de variables d'environnement
    if not tailnet:
        print()
        print(f"{Colors.CYAN}Configuration Tailscale{Colors.NC}")
        print()
        print("Vous pouvez trouver votre tailnet sur:")
        print(f"  {Colors.BLUE}https://login.tailscale.com/admin{Colors.NC}")
        print()
        tailnet = input("Nom du tailnet (ex: example.com ou user@gmail.com): ").strip()

        if not tailnet:
            print_error("Tailnet requis")
            return 1

    if not api_key:
        print()
        print("Créez une clé API sur:")
        print(f"  {Colors.BLUE}https://login.tailscale.com/admin/settings/keys{Colors.NC}")
        print()
        api_key = getpass.getpass("Clé API Tailscale (tskey-api-...): ").strip()

        if not api_key:
            print_error("Clé API requise")
            return 1

    if not target_ip:
        print()
        target_ip = input(
            "IP Tailscale du Raspberry Pi (optionnel, appuyez Entrée pour ignorer): "
        ).strip()
        target_ip = target_ip if target_ip else None

    # Exécuter la vérification
    return asyncio.run(run_verification(tailnet, api_key, target_ip))


if __name__ == "__main__":
    sys.exit(main())
