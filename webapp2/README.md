# WebApp2 - IDS Dashboard + Orchestrateur Pi2/AWS

## 📋 Overview

WebApp2 contient :
- Une API FastAPI (dashboard IDS) + frontend optionnel.
- Un orchestrateur Tkinter qui déploie AWS (ELK), installe la sonde Suricata sur Pi2,
  déploie WebApp2 et sauvegarde la configuration dans la base SQLite.
- Un service systemd pour streamer les logs Suricata vers Elasticsearch.

## 🚀 Démarrage rapide (GUI)

```bash
cd webapp2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 orchestrator_gui.py
```

Le GUI demande immédiatement les credentials, puis déclenche le déploiement.
AWS credentials doivent être disponibles (ex: `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`).
Sur Linux, installez Tk si besoin: `sudo apt install -y python3-tk`.

## 🧩 Structure

```
webapp2/
├── orchestrator_gui.py      # GUI Tkinter (progress + logs)
├── orchestrator.py          # Orchestration AWS + stream Suricata
├── install_pi_probe.sh      # Installation Sonde Pi2
├── main.py                  # FastAPI app
├── start.sh                 # Démarrage local / service
├── requirements.txt         # Dépendances
├── db/
│   ├── database.py          # SQLite wrapper + config
│   └── ids.db              # DB auto-créée
├── api/                     # Endpoints
├── models/                  # Pydantic models
└── frontend/                # React app (build optionnel)
```

## ✅ Déploiement Pi2 (séquence)

1. **Déploiement AWS ELK** (EC2 + Kibana + Elasticsearch)
2. **Installation Sonde Pi2** (Suricata + config réseau)
3. **Déploiement WebApp2** (copie + service systemd)
4. **Streamer Suricata** (service `ids.service`)
5. **Sauvegarde config** (table `deployment_config`)

## 🧹 Reset complet

Le GUI propose un **reset complet** qui supprime :
- Services systemd (`webapp2`, `ids`, `suricata`)
- Répertoire d’installation (`/opt/ids-dashboard` par défaut)
- Paquets liés (suricata, docker, etc.)
- Règles UFW

## 🗄️ Base de données

Tables principales :
- `alerts`
- `system_metrics`
- `deployment_config` (credentials **stockés en clair**)

## 🌐 Endpoints API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/system/health` | GET | CPU, RAM, Disk, Temperature |
| `/api/db/health` | GET | DB health check |
| `/api/alerts/recent` | GET | Recent alerts |
| `/api/alerts/add` | POST | Add test alert |
| `/api/network/stats` | GET | Network stats |
| `/api/pipeline/status` | GET | Pipeline status |

## 🔧 Frontend build (optionnel)

```bash
cd frontend
npm install
npm run build
```

## 📦 Dépendances principales

- `fastapi`, `uvicorn`, `psutil`, `pydantic`
- `boto3`, `elasticsearch`, `requests`, `paramiko`

## 🐳 Docker (optionnel)

`docker-compose.yml` est fourni mais le déploiement GUI ne l’utilise pas.
