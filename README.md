# IDS Agent - Système de Détection d'Intrusion

Agent IDS distribué pour Raspberry Pi avec monitoring Tailscale mesh network.

## 🚀 Quick Start

### Prérequis
- Python 3.10+
- Raspberry Pi 5 (ou compatible)
- Compte Tailscale
- Compte AWS (optionnel)

### Installation

```bash
# Installe les dépendances
pip install -r webapp/backend/requirements.txt

# Configure l'environnement
cp config.yaml.example config.yaml
# Édite config.yaml avec tes paramètres
```

## 📊 Monitoring Tailscale

### Génération du Network Health Map

```bash
# Mode interactif
python scripts/monitor_tailnet.py

# Depuis le code
from ids.monitoring import TailnetMonitor

monitor = TailnetMonitor(api_key="tskey-...", tailnet_name="yourname.ts.net")
snapshot = monitor.get_current_state()
snapshot = monitor.measure_mesh_latency(snapshot)
monitor.generate_interactive_graph(snapshot)
```

### Fonctionnalités

- **Visualisation interactive** : graphe Pyvis avec tous les nœuds Tailscale
- **Mesure de latence** : ping automatique vers tous les nœuds online
- **Taille des nœuds** : proportionnelle à la latence (plus gros = plus rapide)
- **Liens vers console** : clic sur un nœud → console Tailscale
- **Snapshot temporel** : capture l'état du réseau à un instant T

## 🔐 Configuration des Secrets

### Variables d'environnement

```bash
export PI_IP="100.118.244.54"
export PI_USER="pi"
export TS_OAUTH_CLIENT_ID="..."
export TS_OAUTH_CLIENT_SECRET="..."
export TAILSCALE_TAILNET="yourname.ts.net"
export TAILSCALE_API_KEY="tskey-..."
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_REGION="eu-central-1"
```

## 🔧 Secrets Requis

| Secret | Description | Exemple |
|--------|-------------|---------|
| `PI_IP` | IP Tailscale du Pi | `100.118.244.54` |
| `PI_USER` | User SSH du Pi | `pi` |
| `PI` | Clé SSH privée | (contenu de `~/.ssh/pi_ssh_key`) |
| `TS_OAUTH_CLIENT_ID` | OAuth client ID Tailscale | `k...` |
| `TS_OAUTH_CLIENT_SECRET` | OAuth client secret | `tskey-client-...` |
| `TAILSCALE_TAILNET` | Nom du tailnet | `yourname.ts.net` |
| `TAILSCALE_API_KEY` | API key Tailscale | `tskey-api-...` |
| `AWS_ACCESS_KEY_ID` | AWS access key | `AKIA...` |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | `...` |
| `AWS_REGION` | AWS region | `eu-central-1` |
| `AWS_SESSION_TOKEN` | AWS session token (optionnel) | `...` |

### Où récupérer les clés Tailscale

- **OAuth client** : https://login.tailscale.com/admin/oauth-clients
- **API key** : https://login.tailscale.com/admin/settings/keys
- **Tailnet name** : visible dans l'URL de ton admin Tailscale

## 🧪 Tests

```bash
# Tests unitaires
pytest tests/unit/ -v

# Tests d'intégration
pytest tests/integration/ -v

# Coverage
pytest --cov=src/ids --cov-report=html
```

## 🚢 Déploiement

### Manuel

```bash
# Déploiement direct
./deploy/deploy_pi.sh 100.118.244.54

# Avec Tailscale
tailscale up --authkey=tskey-...
./deploy/deploy_pi.sh 100.118.244.54
```

## 📁 Structure du Projet

```
oi/
├── src/ids/
│   ├── monitoring/          # Monitoring Tailscale
│   │   ├── tailnet_monitor.py
│   │   └── __init__.py
│   ├── app/                 # Application layer
│   ├── composants/          # Components (Suricata, Vector, etc.)
│   ├── config/              # Configuration
│   ├── domain/              # Domain models
│   ├── infrastructure/      # Infrastructure (AWS, Redis, etc.)
│   └── interfaces/          # Interfaces/protocols
├── scripts/
│   ├── monitor_tailnet.py   # Script monitoring standalone
│   └── manage_infrastructure.py
├── tests/
│   ├── unit/
│   └── integration/
├── webapp/backend/requirements.txt
└── config.yaml
```

## 🛠️ Développement

### Pre-commit hooks

```bash
pip install pre-commit
pre-commit install
```

### Linting

```bash
black src/ tests/
isort src/ tests/
flake8 src/ tests/
mypy src/ids
```

## 📝 License

MIT

## 🤝 Contribution

Les contributions sont les bienvenues ! Ouvre une issue ou une PR.
