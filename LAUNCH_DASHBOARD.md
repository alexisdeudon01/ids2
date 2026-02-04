# 🚀 Commandes pour lancer le Dashboard IDS

## Option 1 : Lancement direct (Développement)

```bash
# Activer l'environnement virtuel
source webapp/backend/.venv/bin/activate

# Lancer le dashboard
python -m ids.dashboard.main
```

Ou avec uvicorn directement :

```bash
source webapp/backend/.venv/bin/activate
uvicorn ids.dashboard.app:app --host 0.0.0.0 --port 8080 --reload
```

## Option 2 : Installation complète (Production)

```bash
# 1. Exécuter le script de setup
./webapp/backend/scripts/dashboard_setup.sh

# 2. Configurer les variables d'environnement
nano .env
# Éditer avec vos clés API (Elasticsearch, Tailscale, Anthropic)

# 3. Lancer via systemd
sudo systemctl start ids-dashboard
sudo systemctl enable ids-dashboard  # Auto-start au boot

# 4. Voir les logs
sudo journalctl -u ids-dashboard -f
```

## Option 3 : Lancement manuel simple

```bash
# Activer l'environnement virtuel
source webapp/backend/.venv/bin/activate

# Installer les dépendances si nécessaire
pip install -r webapp/backend/requirements.txt

# Lancer
python -m ids.dashboard.main
```

## Configuration automatique de l'infrastructure

Avant de lancer le dashboard, configurez l'infrastructure :

```bash
# Configuration interactive
source webapp/backend/.venv/bin/activate
python webapp/backend/scripts/configure_infrastructure.py
```

Ou via les endpoints API du dashboard :
- `POST /api/setup/infrastructure` - Configuration complète
- `GET /api/setup/tailnet/verify` - Vérifier tailnet
- `POST /api/setup/tailnet/create-key` - Créer clé auth
- `GET /api/setup/opensearch/verify` - Vérifier domaine
- `POST /api/setup/opensearch/create` - Créer domaine

## Configuration (.env)

Créer un fichier `.env` à la racine du projet :

```bash
# Dashboard Configuration
DASHBOARD_PORT=8080
MIRROR_INTERFACE=eth0
LED_PIN=17

# Elasticsearch
ELASTICSEARCH_HOSTS=http://localhost:9200
ELASTICSEARCH_USERNAME=
ELASTICSEARCH_PASSWORD=

# Tailscale
TAILSCALE_TAILNET=votre-tailnet
TAILSCALE_API_KEY=votre-api-key

# Anthropic AI Healing
ANTHROPIC_API_KEY=votre-anthropic-key
```

## Accès au Dashboard

Une fois lancé, ouvrir dans le navigateur :
```
http://localhost:8080
# ou
http://<ip-du-raspberry-pi>:8080
```

## Vérification

```bash
# Vérifier que le serveur répond
curl http://localhost:8080/api/health

# Vérifier les endpoints
curl http://localhost:8080/api/system/health
curl http://localhost:8080/api/pipeline/status
```

## Arrêter le dashboard

```bash
# Si lancé manuellement : Ctrl+C

# Si lancé via systemd
sudo systemctl stop ids-dashboard
```
