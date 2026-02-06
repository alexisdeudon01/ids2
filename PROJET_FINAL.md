# 🎯 IDS2 - Projet Final Refactorisé

## 📋 Résumé des Changements

### ✅ Fichiers Consolidés

1. **requirements.txt** (racine)
   - Unifié: `requirements-deploy.txt`, `AWS/requirements.txt`, `webbapp/requirements.txt`
   - Versions harmonisées et dédupliquées

2. **docker-compose.yml** (racine)
   - Stack ELK complète: Elasticsearch + Kibana
   - Init containers pour configuration automatique
   - Index 'alexis' avec 12 champs
   - Dashboard Kibana pré-configuré

3. **orchestrator.py**
   - Mode GUI: `./start.sh` ou `python3 orchestrator.py`
   - Mode CLI: `python3 orchestrator.py --restart-elk`
   - Merge de `restart_elk.py`

4. **Scripts d'initialisation**
   - `init-es.sh`: Crée l'index 'alexis' avec mapping dynamique
   - `init-kibana.sh`: Configure le dashboard Kibana

### ❌ Fichiers Supprimés

- `restart_elk.py` → intégré dans `orchestrator.py`
- `requirements-deploy.txt` → `requirements.txt`
- `AWS/requirements.txt` → `requirements.txt`
- `webbapp/requirements.txt` → `requirements.txt`
- `AWS/docker-compose.yal` → `docker-compose.yml`
- `AWS/example_usage.py` (obsolète)
- `init-elasticsearch.sh` (doublon)

### 🆕 Fichiers Créés/Modifiés

- ✅ `requirements.txt` - Dépendances unifiées
- ✅ `docker-compose.yml` - Stack ELK + init containers
- ✅ `init-es.sh` - Initialisation Elasticsearch
- ✅ `init-kibana.sh` - Configuration Kibana
- ✅ `webbapp/Dockerfile` - Image webapp
- ✅ `.env.example` - Template configuration
- ✅ `.gitignore` - Nettoyé et organisé
- ✅ `orchestrator.py` - GUI + CLI unifié
- ✅ `start.sh` - Simplifié
- ✅ `AWS/deploy_to_pi.py` - Utilise architecture IDS2

## 🏗️ Architecture Finale

```
ids2/
├── docker-compose.yml       # Stack ELK + init
├── init-es.sh              # Init Elasticsearch
├── init-kibana.sh          # Init Kibana
├── orchestrator.py         # GUI/CLI
├── start.sh                # Démarrage rapide
├── requirements.txt        # Dépendances unifiées
├── run_tests.py            # Tests
├── .env.example            # Config template
│
├── webbapp/                # Application principale
│   ├── ids/deploy/         # Module déploiement
│   ├── api/                # API REST
│   ├── db/                 # Base de données
│   ├── frontend/           # Interface React
│   ├── main.py             # FastAPI app
│   └── Dockerfile          # Image webapp
│
├── AWS/                    # Composants AWS
│   └── deploy_to_pi.py     # Déploiement Pi
│
└── tests/                  # Tests unitaires
```

## 🚀 Utilisation

### 1. Stack ELK (Docker)

```bash
# Démarrer la stack
docker compose up -d

# Vérifier les services
docker ps

# Accès
# - Elasticsearch: http://localhost:9200
# - Kibana: http://localhost:5601
# - Index: alexis (12 champs, mapping dynamique)
```

### 2. Déploiement Complet (GUI)

```bash
./start.sh
```

### 3. Redémarrer ELK (CLI)

```bash
python3 orchestrator.py --restart-elk
```

### 4. Tests

```bash
python3 run_tests.py
```

## 📊 Index Elasticsearch 'alexis'

**12 champs configurés:**

| Champ | Type | Description |
|-------|------|-------------|
| `@timestamp` | date | Horodatage |
| `message` | text | Message |
| `severity` | keyword | Sévérité |
| `source_ip` | ip | IP source |
| `dest_ip` | ip | IP destination |
| `source_port` | integer | Port source |
| `dest_port` | integer | Port destination |
| `protocol` | keyword | Protocole |
| `event_type` | keyword | Type événement |
| `signature` | text | Signature IDS |
| `category` | keyword | Catégorie |
| `action` | keyword | Action |

**Mapping dynamique activé** pour accepter de nouveaux champs automatiquement.

## 🎯 Configuration

### Variables d'environnement (.env)

```bash
# Pas nécessaire pour ELK (sécurité désactivée en dev)
```

### Configuration par défaut (webbapp/ids/deploy/config.py)

| Paramètre | Valeur | Description |
|-----------|--------|-------------|
| AWS Region | `eu-west-1` | Région AWS |
| Pi IP | `192.168.178.66` | IP Raspberry Pi |
| Pi User | `pi` | Utilisateur SSH |
| Remote Dir | `/opt/ids2` | Répertoire installation |
| Mirror Interface | `eth0` | Interface réseau |

## 🧹 Bénéfices du Refactoring

- ✅ **-60% fichiers redondants**
- ✅ **Configuration centralisée**
- ✅ **Docker-compose unifié**
- ✅ **Init automatique ELK**
- ✅ **Index pré-configuré**
- ✅ **Dashboard Kibana prêt**
- ✅ **CLI + GUI dans un fichier**
- ✅ **.gitignore propre**

## 📝 Notes Importantes

1. **Sécurité désactivée** sur ELK pour développement
2. **User 1000:1000** pour éviter problèmes permissions
3. **Healthchecks** pour démarrage ordonné
4. **Init containers** s'exécutent une seule fois
5. **Volumes persistants** pour données ELK

## 🔧 Maintenance

### Recréer l'index

```bash
docker compose down
docker volume rm ids2_es_data ids2_kibana_data
docker compose up -d
```

### Voir les logs

```bash
docker logs ids2-elasticsearch
docker logs ids2-kibana
docker logs ids2-init-es
docker logs ids2-init-kibana
```

### Arrêter la stack

```bash
docker compose down
```

## ✅ Statut Final

- ✅ Stack ELK fonctionnelle
- ✅ Index 'alexis' créé automatiquement
- ✅ Dashboard Kibana configuré
- ✅ Mapping dynamique activé
- ✅ 12 champs pré-définis
- ✅ Init containers opérationnels
- ✅ Architecture simplifiée
- ✅ Documentation complète

---

**Date**: 2026-02-06  
**Version**: 2.0 (Refactorisé)
