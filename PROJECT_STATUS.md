# IDS2 Project - Clean Architecture

## ✅ Structure Finale

```
ids2/
├── orchestrator.py              # 🚀 Main entry point (GUI)
├── requirements-deploy.txt      # Dependencies
├── DEPLOYMENT.md               # Documentation
│
├── webapp/backend/src/ids/
│   ├── __init__.py             # Root package
│   └── deploy/                 # ✅ Deployment module (ONLY active package)
│       ├── __init__.py         # Lazy loading
│       ├── config.py           # Configuration with defaults
│       ├── ssh_client.py       # SSH operations
│       ├── aws_deployer.py     # AWS ELK deployment
│       ├── pi_deployer.py      # Raspberry Pi setup
│       ├── orchestrator.py     # Orchestration facade
│       └── gui.py              # Tkinter GUI
│
└── webbapp/                    # Legacy webapp (separate)
    ├── main.py
    ├── api/
    ├── db/
    └── frontend/

```

## 🎯 Valeurs par Défaut

| Paramètre | Valeur | Description |
|-----------|--------|-------------|
| `aws_region` | `eu-west-1` | Région AWS pour ELK |
| `pi_host` | `sinik` | Hostname du Raspberry Pi |
| `pi_ip` | `192.168.178.66` | IP du Raspberry Pi |
| `pi_user` | `pi` | Utilisateur SSH |
| `pi_password` | `pi` | Mot de passe SSH |
| `sudo_password` | `pi` | Mot de passe sudo |
| `remote_dir` | `/opt/ids2` | Répertoire d'installation |
| `mirror_interface` | `eth0` | Interface réseau pour capture |
| `elastic_password` | *(requis)* | Mot de passe Elasticsearch |

## 🚀 Usage

```bash
# Install dependencies
pip install -r requirements-deploy.txt

# Run GUI
python3 orchestrator.py
```

## ✅ Tests Effectués

- ✅ Config avec valeurs par défaut
- ✅ Lazy loading des modules
- ✅ Structure minimale (deploy uniquement)
- ✅ GUI avec labels explicatifs

## 📝 Mirror Interface

L'interface réseau (`eth0` par défaut) qui reçoit le trafic miroir depuis votre switch réseau via SPAN/port mirroring. Configure votre switch pour envoyer une copie du trafic vers le port où le Pi est connecté.

## 🧹 Nettoyage Effectué

- ❌ Supprimé : packages vides (app, domain, interfaces, etc.)
- ✅ Conservé : deploy/ (seul package actif)
- ✅ Ajouté : orchestrator.py (point d'entrée racine)
- ✅ Ajouté : Documentation complète
