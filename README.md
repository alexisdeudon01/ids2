# IDS2 - Intrusion Detection System

## 🏗️ Architecture Propre

```
ids2/
├── orchestrator.py          # 🚀 GUI principale
├── run_tests.py             # 🧪 Lanceur de tests
├── requirements-deploy.txt  # 📦 Dépendances
│
├── webbapp/                 # Application principale
│   ├── ids/deploy/          # Module de déploiement
│   ├── api/                 # API REST
│   ├── db/                  # Base de données
│   ├── frontend/            # Interface React
│   └── main.py              # FastAPI app
│
└── tests/                   # 🧪 Tests unitaires
    ├── test_config.py
    └── test_integration.py
```

## ✅ Tests Unitaires

```bash
# Lancer tous les tests
python3 run_tests.py

# Résultat attendu: 7 tests OK
```

## 🚀 Démarrage Rapide

### 1. Lancer l'orchestrateur (UI)

```bash
./start.sh
```

Les valeurs par défaut peuvent être personnalisées dans `config.json` à la racine.

## 📋 Configuration par Défaut

| Paramètre | Valeur | Description |
|-----------|--------|-------------|
| **AWS Region** | `u-west-1` | Région AWS pour ELK |
| **Pi Hostname** | `sinik` | Nom d'hôte du Raspberry Pi |
| **Pi IP** | `192.168.178.66` | Adresse IP du Raspberry Pi |
| **Pi User** | `pi` | Utilisateur SSH |
| **Pi Password** | `pi` | Mot de passe SSH |
| **Sudo Password** | `pi` | Mot de passe sudo |
| **Remote Dir** | `/opt/ids2` | Répertoire d'installation |
| **Mirror Interface** | `eth0` | Interface réseau pour capture |
| **Elastic Password** | *(requis)* | Mot de passe Elasticsearch |
| **SSH Key Path** | `/home/tor/.ssh/pi_key` | Chemin clé privée si SSH sans mot de passe |

Les credentials AWS peuvent être fournis via variables d'environnement :
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`.

## 🔍 Mirror Interface

L'interface réseau (`eth0` par défaut) qui reçoit le trafic miroir depuis votre switch réseau.

**Configuration requise :**
1. Configurez votre switch pour activer le port mirroring (SPAN)
2. Dirigez le trafic miroir vers le port où le Pi est connecté
3. L'interface sera automatiquement mise en mode promiscuous

**Interfaces courantes :**
- `eth0` : Ethernet filaire (recommandé)
- `wlan0` : WiFi (non recommandé pour IDS)

## 🧪 Tests

### Tests de Configuration
- ✅ Valeurs par défaut
- ✅ Valeurs personnalisées
- ✅ Flags booléens
- ✅ Lazy loading

### Tests d'Intégration
- ✅ Création de config minimale
- ✅ Personnalisation complète
- ✅ Import lazy

## 📦 Modules

### `ids/deploy/`
- **config.py** : Configuration avec valeurs par défaut
- **ssh_client.py** : Client SSH/SFTP
- **aws_deployer.py** : Déploiement ELK sur AWS
- **pi_deployer.py** : Installation sur Raspberry Pi
- **orchestrator.py** : Orchestration du déploiement
- **gui.py** : Interface Tkinter

## 🎯 Fonctionnalités

- ✅ Déploiement ELK sur AWS EC2
- ✅ Configuration Elasticsearch (mappings, rétention)
- ✅ Installation Suricata IDS sur Pi
- ✅ Déploiement webapp & streamer
- ✅ Gestion Docker (install/remove)
- ✅ Reset complet
- ✅ Tests unitaires
- ✅ Valeurs par défaut intelligentes

## 🧹 Nettoyage Effectué

- ❌ Supprimé : Répertoire `webapp/` dupliqué
- ❌ Supprimé : Packages vides (app, domain, interfaces, etc.)
- ✅ Consolidé : Tout dans `webbapp/`
- ✅ Ajouté : Tests unitaires complets
- ✅ Ajouté : Documentation complète

## 📊 Résultats des Tests

```
test_boolean_flags ... ok
test_boolean_flags_custom ... ok
test_custom_values ... ok
test_default_values ... ok
test_config_creation_minimal ... ok
test_config_full_customization ... ok
test_lazy_import_config ... ok

----------------------------------------------------------------------
Ran 7 tests in 0.000s

OK ✅
```

## 🚀 Prêt pour Production

Le projet est maintenant :
- ✅ Nettoyé et refactorisé
- ✅ Testé (7/7 tests passent)
- ✅ Documenté
- ✅ Prêt à déployer
