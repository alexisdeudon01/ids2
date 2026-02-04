#!/usr/bin/env python3
"""
Exemple de déploiement complet utilisant tous les gestionnaires.

Ce script montre comment orchestrer :
1. Vérification du réseau Tailscale
2. Création du domaine OpenSearch
3. Déploiement sur le Raspberry Pi
"""

import asyncio
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ids.managers import (
    OpenSearchDomainManager,
    RaspberryPiManager,
    TailscaleManager,
)


async def deploy_full_stack():
    """Déploiement complet de la stack IDS."""

    print("=" * 70)
    print("🚀 IDS Full Stack Deployment")
    print("=" * 70)

    # =========================================================================
    # 1. Configuration
    # =========================================================================

    print("\n📝 Configuration\n")

    # Tailscale
    ts_api_key = getpass.getpass("Tailscale API Key: ")
    ts_tailnet = input("Tailscale Tailnet: ").strip()

    # Pi
    pi_ip = input("Pi Tailscale IP (default: 100.118.244.54): ").strip() or "100.118.244.54"
    pi_user = input("Pi User (default: pi): ").strip() or "pi"
    pi_ssh_key = (
        input("SSH Key (default: ~/.ssh/pi_ssh_key): ").strip() or "~/.ssh/pi_ssh_key"
    )
    pi_ssh_key = str(Path(pi_ssh_key).expanduser())

    # AWS (optionnel)
    aws_key = input("AWS Access Key (press Enter to skip): ").strip()
    aws_secret = None
    aws_region = "eu-central-1"
    if aws_key:
        aws_secret = getpass.getpass("AWS Secret Key: ")
        aws_region = input("AWS Region (default: eu-central-1): ").strip() or "eu-central-1"

    # =========================================================================
    # 2. Vérification Tailscale
    # =========================================================================

    print("\n" + "=" * 70)
    print("📡 Step 1: Tailscale Network Check")
    print("=" * 70)

    async with TailscaleManager(ts_api_key, ts_tailnet) as ts_manager:
        # Lister les devices
        devices = await ts_manager.list_devices()
        print(f"\n✅ Found {len(devices)} devices in tailnet")

        # Trouver le Pi
        pi_device = await ts_manager.find_device_by_ip(pi_ip)
        if not pi_device:
            print(f"❌ Pi not found at {pi_ip}")
            print("\n💡 Available devices:")
            for device in devices:
                ip = device.addresses[0] if device.addresses else "N/A"
                print(f"   • {device.name}: {ip}")
            return

        print(f"✅ Pi found: {pi_device.name}")
        print(f"   IP: {pi_device.addresses[0]}")
        print(f"   OS: {pi_device.os}")
        print(f"   Status: {'🟢 Online' if pi_device.online else '🔴 Offline'}")

        # Ping le Pi
        print(f"\n📡 Pinging Pi...")
        latency = ts_manager.ping_device(pi_ip, count=4)
        if latency:
            print(f"✅ Ping successful: {latency:.2f}ms")
        else:
            print(f"❌ Ping failed")
            return

        # Vérifier les tags
        if not pi_device.tags:
            print(f"\n⚠️  No tags on Pi device. Adding tags...")
            await ts_manager.set_device_tags(pi_device.device_id, ["tag:raspberry-pi", "tag:ids"])
            print(f"✅ Tags added")

    # =========================================================================
    # 3. AWS OpenSearch (optionnel)
    # =========================================================================

    opensearch_endpoint = None
    if aws_key and aws_secret:
        print("\n" + "=" * 70)
        print("🔍 Step 2: AWS OpenSearch Setup")
        print("=" * 70)

        os_manager = OpenSearchDomainManager(
            aws_access_key_id=aws_key, aws_secret_access_key=aws_secret, region=aws_region
        )

        domain_name = "suricata-prod"
        print(f"\n🔨 Creating/verifying domain: {domain_name}")

        try:
            status = os_manager.create_domain(
                domain_name=domain_name,
                instance_type="t3.small.search",
                instance_count=1,
                volume_size_gb=10,
                wait=True,
                timeout=1800,
            )

            opensearch_endpoint = status.endpoint
            print(f"✅ Domain ready: {opensearch_endpoint}")

            # Test connectivity
            if os_manager.ping_domain(opensearch_endpoint):
                print(f"✅ OpenSearch accessible")
            else:
                print(f"⚠️  OpenSearch not yet accessible (may need time)")

        except Exception as e:
            print(f"❌ OpenSearch setup failed: {e}")
            print(f"⚠️  Continuing without OpenSearch...")
    else:
        print("\n⏭️  Skipping AWS OpenSearch (no credentials)")

    # =========================================================================
    # 4. Déploiement sur le Pi
    # =========================================================================

    print("\n" + "=" * 70)
    print("🍓 Step 3: Raspberry Pi Deployment")
    print("=" * 70)

    with RaspberryPiManager(pi_ip, pi_user, ssh_key_path=pi_ssh_key) as pi:
        # Infos système
        print(f"\n📊 System Information")
        info = pi.get_system_info()
        print(f"   Model: {info.model}")
        print(f"   OS: {info.os_version}")
        print(f"   CPUs: {info.cpu_count}")
        print(f"   Memory: {info.total_memory_mb} MB")
        if info.cpu_temperature:
            print(f"   Temperature: {info.cpu_temperature:.1f}°C")

        # Créer les répertoires
        print(f"\n📁 Creating directories...")
        pi.ensure_directory("/opt/ids", sudo=True)
        pi.ensure_directory("/opt/ids/docker", sudo=True)
        pi.ensure_directory("/opt/ids/logs", sudo=True)
        pi.set_owner("/opt/ids", f"{pi_user}:{pi_user}", sudo=True)
        print(f"✅ Directories created")

        # Upload des fichiers
        print(f"\n📤 Uploading configuration...")
        # Note: Dans un vrai déploiement, tu uploaderais les fichiers réels
        print(f"   (Skipped in example - use pi.upload_file() or pi.upload_directory())")

        # Vérifier Docker
        print(f"\n🐳 Checking Docker...")
        containers = pi.list_containers()
        print(f"✅ Docker accessible ({len(containers)} containers)")

        # Vérifier les services
        print(f"\n⚙️  Checking services...")
        services = ["docker.service", "ids2-agent.service", "suricata.service"]
        for service_name in services:
            try:
                status = pi.get_service_status(service_name)
                status_icon = "✅" if status.active else "⚠️ "
                print(
                    f"   {status_icon} {service_name}: {'active' if status.active else 'inactive'}"
                )
            except Exception:
                print(f"   ⚠️  {service_name}: not found")

    # =========================================================================
    # 5. Résumé
    # =========================================================================

    print("\n" + "=" * 70)
    print("✅ Deployment Summary")
    print("=" * 70)
    print(f"\n✅ Tailscale: {pi_device.name} ({pi_ip}) - {latency:.2f}ms")
    if opensearch_endpoint:
        print(f"✅ OpenSearch: {opensearch_endpoint}")
    print(f"✅ Raspberry Pi: {info.model} - {info.cpu_temperature:.1f}°C")
    print(f"\n🎉 Deployment complete!")


if __name__ == "__main__":
    try:
        asyncio.run(deploy_full_stack())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
