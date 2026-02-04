#!/usr/bin/env python3
"""
Script de configuration automatique de l'infrastructure IDS.

Configure:
- Tailscale tailnet
- OpenSearch/Elasticsearch domain
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ids.dashboard.setup import OpenSearchSetup, TailnetSetup, setup_infrastructure

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


async def main() -> None:
    """Main configuration function."""
    print("🚀 Configuration de l'infrastructure IDS\n")

    # Get configuration from environment or prompt
    tailnet = os.getenv("TAILSCALE_TAILNET")
    tailscale_api_key = os.getenv("TAILSCALE_API_KEY")
    opensearch_domain = os.getenv("OPENSEARCH_DOMAIN_NAME")
    config_path = Path("config.yaml")

    if not tailnet:
        tailnet = input("Nom du Tailnet Tailscale: ").strip()
    if not tailscale_api_key:
        tailscale_api_key = input("Clé API Tailscale: ").strip()

    if not opensearch_domain:
        opensearch_domain = input("Nom du domaine OpenSearch (optionnel, laisser vide pour utiliser config.yaml): ").strip() or None

    print("\n📡 Configuration du Tailnet Tailscale...")
    tailnet_setup = TailnetSetup(tailnet, tailscale_api_key)
    tailnet_result = await tailnet_setup.verify_tailnet()

    if tailnet_result.get("configured"):
        print(f"✅ Tailnet '{tailnet_result['tailnet']}' vérifié ({tailnet_result['node_count']} nœuds)")
    else:
        print(f"❌ Erreur Tailnet: {tailnet_result.get('error', 'Unknown error')}")
        print("   Vérifiez TAILSCALE_TAILNET et TAILSCALE_API_KEY")

    print("\n🔍 Configuration du domaine OpenSearch...")
    opensearch_setup = OpenSearchSetup(config_path)
    opensearch_result = await opensearch_setup.verify_domain(opensearch_domain)

    if opensearch_result.get("configured"):
        print(f"✅ Domaine OpenSearch '{opensearch_result['domain_name']}' vérifié")
        print(f"   Endpoint: {opensearch_result.get('endpoint', 'N/A')}")
    else:
        print(f"⚠️  Domaine OpenSearch non trouvé: {opensearch_result.get('error', 'Unknown error')}")
        create = input("   Voulez-vous créer le domaine? (o/n): ").strip().lower()
        if create == "o":
            domain_name = opensearch_domain or input("Nom du domaine à créer: ").strip()
            print(f"   Création du domaine '{domain_name}' (cela peut prendre 15-30 minutes)...")
            create_result = await opensearch_setup.create_domain(domain_name, wait=True, timeout=1800)
            if create_result.get("success"):
                print(f"✅ Domaine créé avec succès!")
                print(f"   Endpoint: {create_result.get('endpoint', 'N/A')}")
            else:
                print(f"❌ Erreur lors de la création: {create_result.get('error', 'Unknown error')}")

    print("\n✨ Configuration terminée!")


if __name__ == "__main__":
    asyncio.run(main())
