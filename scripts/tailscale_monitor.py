#!/usr/bin/env python3
"""
Tailscale Network Monitor - CLI Entry Point.

This script uses the SOLID-compliant ids.tailscale module.

Usage:
    python scripts/tailscale_monitor.py                    # Interactive mode
    python scripts/tailscale_monitor.py --check IP        # Check specific device
    
Environment Variables:
    TAILSCALE_TAILNET - Tailnet name
    TAILSCALE_API_KEY - API key
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ids.tailscale import TailnetMonitor, run_monitor_async


def get_credentials() -> tuple[str, str]:
    """Get credentials from environment or prompt."""
    tailnet = os.environ.get("TAILSCALE_TAILNET")
    api_key = os.environ.get("TAILSCALE_API_KEY")
    
    if not tailnet:
        tailnet = input("📡 Enter Tailnet Name: ").strip()
    
    if not api_key:
        api_key = getpass.getpass("🔑 Enter Tailscale API Key: ")
    
    return tailnet, api_key


async def check_connectivity(tailnet: str, api_key: str, target_ip: str) -> int:
    """Check connectivity to a specific device."""
    print(f"🔍 Checking connectivity to {target_ip}...")
    print()
    
    monitor = TailnetMonitor(tailnet=tailnet, api_key=api_key)
    success = await monitor.check_device_connectivity(target_ip)
    
    return 0 if success else 1


async def full_monitor(tailnet: str, api_key: str, output: str) -> int:
    """Run full monitoring cycle."""
    try:
        await run_monitor_async(tailnet, api_key, output)
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Tailscale Network Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              Run interactive monitoring
  %(prog)s --check 100.64.1.2           Check specific device connectivity
  %(prog)s -o my_network.html           Custom output file
        """,
    )
    
    parser.add_argument(
        "--check", "-c",
        metavar="IP",
        help="Check connectivity to a specific Tailscale IP",
    )
    parser.add_argument(
        "--output", "-o",
        default="network_health_map.html",
        help="Output HTML file (default: network_health_map.html)",
    )
    parser.add_argument(
        "--tailnet", "-t",
        help="Tailnet name (or set TAILSCALE_TAILNET env var)",
    )
    parser.add_argument(
        "--api-key", "-k",
        help="API key (or set TAILSCALE_API_KEY env var)",
    )
    
    args = parser.parse_args()
    
    # Get credentials
    tailnet = args.tailnet or os.environ.get("TAILSCALE_TAILNET")
    api_key = args.api_key or os.environ.get("TAILSCALE_API_KEY")
    
    if not tailnet or not api_key:
        print("=" * 60)
        print("  🌐 TAILSCALE MESH NETWORK MONITOR")
        print("=" * 60)
        print()
        
        if not tailnet:
            tailnet = input("📡 Enter Tailnet Name: ").strip()
        if not api_key:
            api_key = getpass.getpass("🔑 Enter Tailscale API Key: ")
        print()
    
    if not tailnet or not api_key:
        print("❌ Tailnet and API key are required.")
        return 1
    
    # Run appropriate mode
    if args.check:
        return asyncio.run(check_connectivity(tailnet, api_key, args.check))
    else:
        return asyncio.run(full_monitor(tailnet, api_key, args.output))


if __name__ == "__main__":
    sys.exit(main())
