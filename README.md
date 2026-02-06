# IDS2 - Intrusion Detection System

## 🏗️ Architecture

```
ids2/
├── orchestrator.py          # 🚀 GUI/CLI principale
├── run_tests.py             # 🧪 Tests
├── requirements.txt         # 📦 Dépendances unifiées
├── docker-compose.yml       # 🐳 Stack complète (ELK + Webapp)
├── start.sh                 # 🎬 Démarrage rapide
│
├── webbapp/                 # Application principale
│   ├── ids/deploy/          # Module de déploiement
│   ├── api/                 # API REST
│   ├── db/                  # Base de données
│   ├── frontend/            # Interface React
│   ├── main.py              # FastAPI app
│   └── Dockerfile           # Image webapp
│
├── AWS/                     # Composants AWS (legacy)
└── tests/                   # 🧪 Tests unitaires
```

## 🚀 Démarrage Rapide

### 1. Stack locale (Docker)

```bash
# Copier la config
cp .env.example .env

# Démarrer ELK + Webapp
docker-compose up -d

# Accès
# - Webapp: http://localhost:8000
# - Kibana: http://localhost:5601
# - Elasticsearch: http://localhost:9200
```

### 2. Déploiement complet (GUI)

```bash
./start.sh
```

### 3. Redémarrer ELK (CLI)

```bash
python3 orchestrator.py --restart-elk
```

## ✅ Tests

```bash
python3 run_tests.py
```

## 📋 Configuration

Valeurs par défaut dans `webbapp/ids/deploy/config.py`:

| Paramètre | Valeur | Description |
|-----------|--------|-------------|
| **AWS Region** | `eu-west-1` | Région AWS |
| **Pi IP** | `192.168.178.66` | IP du Raspberry Pi |
| **Pi User** | `pi` | Utilisateur SSH |
| **Remote Dir** | `/opt/ids2` | Répertoire d'installation |
| **Mirror Interface** | `eth0` | Interface réseau |

Variables d'environnement:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `ELASTIC_PASSWORD`

## 🎯 Fonctionnalités

- ✅ Stack ELK locale (Docker)
- ✅ Déploiement ELK sur AWS EC2
- ✅ Installation Suricata IDS sur Pi
- ✅ Webapp FastAPI + React
- ✅ GUI Tkinter pour orchestration
- ✅ Tests unitaires complets

## 🧹 Nettoyage

- ❌ Supprimé: Fichiers requirements redondants
- ❌ Supprimé: docker-compose.yal (AWS legacy)
- ❌ Supprimé: example_usage.py
- ❌ Supprimé: restart_elk.py (intégré dans orchestrator)
- ✅ Unifié: requirements.txt à la racine
- ✅ Créé: docker-compose.yml global
- ✅ Mis à jour: .gitignore
