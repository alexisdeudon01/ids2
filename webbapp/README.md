# Webbapp - IDS Dashboard + Orchestrateur Pi2/AWS

## 📋 Overview

Webbapp contient :
- Une API FastAPI (dashboard IDS) + frontend optionnel.
- Un orchestrateur Tkinter qui déploie AWS (ELK), installe la sonde Suricata sur Pi2,
  déploie Webbapp et sauvegarde la configuration dans la base SQLite.
- Un service systemd pour streamer les logs Suricata vers Elasticsearch.

## 🚀 Démarrage rapide (GUI)

```bash
cd /home/tor/Downloads/ids2
./start.sh
```

`start.sh` est l’unique script d’entrée et lance l’UI d’installation.

Le GUI demande immédiatement les credentials, puis déclenche le déploiement.
AWS credentials doivent être disponibles (ex: `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`).
Sur Linux, installez Tk si besoin: `sudo apt install -y python3-tk`.
Le démarrage utilise l'environnement Python système (pas de venv).
Les valeurs par défaut peuvent être définies dans `config.json` (racine du projet).

## 🧩 Structure

```
webbapp/
├── ids/
│   └── deploy/              # Orchestrator (GUI, AWS, Pi, SSH)
├── main.py                  # FastAPI app
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
3. **Déploiement Webbapp** (copie + service systemd)
4. **Streamer Suricata** (service `ids.service`)
5. **Sauvegarde config** (table `deployment_config`)

## 🧹 Reset complet

Le GUI propose un **reset complet** qui supprime :
- Services systemd (`webbapp`, `ids`, `suricata`)
- Répertoire d’installation (`/opt/ids2` par défaut)
- Paquets liés (suricata, docker, etc.)
- Règles UFW

Si la Pi refuse l'authentification par mot de passe, renseignez **SSH Key Path**.

Le GUI propose aussi des actions dédiées **Installer Docker** et **Supprimer Docker**.

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

Chaque route frontend dispose d'un fichier dédié dans `frontend/src/routes`.

## 📦 Dépendances principales

- `fastapi`, `uvicorn`, `psutil`, `pydantic`
- `boto3`, `elasticsearch`, `requests`, `paramiko`

## 🐳 Docker

Docker a été retiré pour simplifier le déploiement local et sur Pi2.

## 🧭 Diagrammes

Les diagrammes de machine à états et de classes sont disponibles dans `DIAGRAMS.md`.
