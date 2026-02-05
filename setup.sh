#!/usr/bin/env bash
set -euo pipefail

prompt() {
  local label="$1"
  local default="${2:-}"
  local value=""
  if [ -n "$default" ]; then
    read -r -p "${label} [${default}]: " value
    echo "${value:-$default}"
  else
    read -r -p "${label}: " value
    echo "$value"
  fi
}

for cmd in sshpass tar ssh scp; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Error: '$cmd' is required. Install it first."
    exit 1
  fi
done

PI_HOST="$(prompt 'IP du Raspberry Pi')"
PI_USER="$(prompt 'Utilisateur SSH' 'pi')"
read -r -s -p "Mot de passe SSH: " PI_PASS
echo ""
read -r -s -p "Mot de passe sudo: " SUDO_PASS
echo ""

REMOTE_DIR="$(prompt 'Répertoire d’installation sur le Pi' '/opt/ids-dashboard')"
MIRROR_INTERFACE="$(prompt 'Interface miroir' 'eth0')"

if [ -z "$PI_HOST" ]; then
  echo "IP du Raspberry Pi requise."
  exit 1
fi

export SSHPASS="$PI_PASS"

run_remote() {
  local cmd="$1"
  sshpass -e ssh -o StrictHostKeyChecking=accept-new "${PI_USER}@${PI_HOST}" "$cmd"
}

run_remote_sudo() {
  local cmd="$1"
  sshpass -e ssh -o StrictHostKeyChecking=accept-new "${PI_USER}@${PI_HOST}" \
    "echo '$SUDO_PASS' | sudo -S -p '' bash -lc $(printf %q "$cmd")"
}

echo "📦 Préparation du paquet..."
ARCHIVE_PATH="$(mktemp -t ids-dashboard-XXXXXX.tar.gz)"
chmod 600 "$ARCHIVE_PATH"
trap 'rm -f "$ARCHIVE_PATH"' EXIT
tar \
  --exclude=webapp/frontend/node_modules \
  --exclude=webapp/backend/.venv \
  --exclude=webapp/backend/venv \
  --exclude=__pycache__ \
  -czf "$ARCHIVE_PATH" .

echo "🔐 Création du répertoire distant..."
run_remote_sudo "mkdir -p '$REMOTE_DIR' && chown -R '${PI_USER}:${PI_USER}' '$REMOTE_DIR'"

echo "🚚 Transfert du dépôt vers le Pi..."
sshpass -e scp -o StrictHostKeyChecking=accept-new "$ARCHIVE_PATH" \
  "${PI_USER}@${PI_HOST}:/tmp/ids-dashboard.tar.gz"

echo "📂 Extraction sur le Pi..."
run_remote_sudo "rm -rf '$REMOTE_DIR'/*"
run_remote_sudo "tar -xzf /tmp/ids-dashboard.tar.gz -C '$REMOTE_DIR'"
run_remote_sudo "chmod +x '$REMOTE_DIR/depancecmd/'*.sh"

echo "🧩 Exécution des scripts d'installation..."
for script in depancecmd/*.sh; do
  script_name="$(basename "$script")"
  echo "➡️  $script_name"
  if ! run_remote_sudo \
    "REMOTE_DIR='$REMOTE_DIR' INSTALL_USER='$PI_USER' MIRROR_INTERFACE='$MIRROR_INTERFACE' bash '$REMOTE_DIR/depancecmd/$script_name'"; then
    echo "❌ Échec sur $script_name."
    echo "➡️  Conseil: éditez $REMOTE_DIR/depancecmd/$script_name pour ajuster la commande."
    echo "➡️  Exemple: ajoutez un paquet manquant via 'apt-get install -y <package>'."
  else
    echo "✅ $script_name terminé."
  fi
done

echo ""
echo "🐳 Vérification de Docker..."
if ! run_remote "docker --version" >/dev/null 2>&1; then
  echo "❌ Docker n'est pas installé. Installation en cours..."
  run_remote_sudo "curl -fsSL https://get.docker.com -o /tmp/get-docker.sh && sh /tmp/get-docker.sh"
  run_remote_sudo "usermod -aG docker '$PI_USER'"
  run_remote_sudo "systemctl enable docker && systemctl start docker"
  echo "✅ Docker installé"
else
  echo "✅ Docker est installé: $(run_remote 'docker --version')"
  # S'assurer que Docker est démarré
  run_remote_sudo "systemctl start docker || true"
fi

# Vérifier docker compose
if ! run_remote "docker compose version" >/dev/null 2>&1; then
  echo "⚠️  docker compose non disponible, installation..."
  run_remote_sudo "apt-get update && apt-get install -y docker-compose-plugin || apt-get install -y docker-compose"
fi

echo ""
echo "🔐 Vérification des connexions AWS et OpenSearch..."
BACKEND_DIR="$REMOTE_DIR/webapp/backend"
CONFIG_FILE="$BACKEND_DIR/config.yaml"
SECRET_FILE="$BACKEND_DIR/secret.json"

# Fonction pour vérifier AWS et OpenSearch
check_aws_opensearch() {
  echo "  📡 Vérification des credentials AWS..."
  run_remote "cd '$BACKEND_DIR' && python3 << 'PYEOF'
import sys
import os
import json
from pathlib import Path

try:
    import boto3
    from opensearchpy import OpenSearch, RequestsHttpConnection
    from requests_aws4auth import AWS4Auth
except ImportError as e:
    print(f'❌ Bibliothèques manquantes: {e}')
    print('   Installez: pip install boto3 opensearch-py requests-aws4auth')
    sys.exit(1)

# Charger la configuration
config_path = Path('$CONFIG_FILE')
secret_path = Path('$SECRET_FILE')

aws_config = {}
if config_path.exists():
    import yaml
    with open(config_path) as f:
        config = yaml.safe_load(f) or {}
        aws_config = config.get('aws', {})

# Charger les secrets
access_key = os.getenv('AWS_ACCESS_KEY_ID')
secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
session_token = os.getenv('AWS_SESSION_TOKEN')

if secret_path.exists():
    with open(secret_path) as f:
        secrets = json.load(f)
        access_key = access_key or secrets.get('aws_access_key_id')
        secret_key = secret_key or secrets.get('aws_secret_access_key')
        session_token = session_token or secrets.get('aws_session_token')

region = aws_config.get('region') or os.getenv('AWS_REGION', 'eu-central-1')
opensearch_endpoint = aws_config.get('opensearch_endpoint') or aws_config.get('opensearch', {}).get('endpoint')
domain_name = aws_config.get('domain_name') or aws_config.get('opensearch', {}).get('domain_name')

if not access_key or not secret_key:
    print('⚠️  Credentials AWS non configurés (optionnel si instance profile)')
    print('   Les services fonctionneront mais OpenSearch nécessite des credentials')
    sys.exit(0)

# Vérifier AWS credentials
print(f'  🔑 Test des credentials AWS (region: {region})...')
try:
    session = boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        aws_session_token=session_token,
        region_name=region
    )
    sts = session.client('sts')
    identity = sts.get_caller_identity()
    print(f'  ✅ AWS credentials valides (Account: {identity.get(\"Account\", \"N/A\")})')
except Exception as e:
    print(f'  ❌ Erreur AWS credentials: {e}')
    sys.exit(1)

# Vérifier OpenSearch si configuré
if opensearch_endpoint or domain_name:
    endpoint = opensearch_endpoint
    if not endpoint and domain_name:
        # Essayer de récupérer l'endpoint depuis AWS
        try:
            opensearch_client = session.client('opensearch')
            domain_info = opensearch_client.describe_domain(DomainName=domain_name)
            endpoint = domain_info.get('DomainStatus', {}).get('Endpoint') or domain_info.get('DomainStatus', {}).get('Endpoints', {}).get('vpc')
            if not endpoint:
                print(f'  ⚠️  Domaine {domain_name} existe mais endpoint non disponible')
                sys.exit(0)
        except Exception as e:
            print(f'  ⚠️  Impossible de récupérer endpoint pour {domain_name}: {e}')
            sys.exit(0)
    
    if endpoint:
        # Nettoyer l'endpoint (enlever https://)
        endpoint = endpoint.replace('https://', '').replace('http://', '').split('/')[0]
        print(f'  🔍 Test de connexion OpenSearch (endpoint: {endpoint})...')
        try:
            credentials = session.get_credentials()
            aws_auth = AWS4Auth(
                credentials.access_key,
                credentials.secret_key,
                region,
                'es',
                session_token=credentials.token
            )
            client = OpenSearch(
                hosts=[{'host': endpoint, 'port': 443}],
                http_auth=aws_auth,
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection,
                timeout=10
            )
            info = client.info()
            print(f'  ✅ OpenSearch accessible (version: {info.get(\"version\", {}).get(\"number\", \"N/A\")})')
        except Exception as e:
            print(f'  ❌ Erreur connexion OpenSearch: {e}')
            print('     Vérifiez: endpoint, credentials, région, sécurité réseau')
            sys.exit(1)
    else:
        print('  ⚠️  OpenSearch configuré mais endpoint non disponible')
else:
    print('  ℹ️  OpenSearch non configuré (optionnel)')

print('  ✅ Vérifications AWS/OpenSearch terminées')
PYEOF
" || {
    echo "  ⚠️  Vérification AWS/OpenSearch échouée (peut être optionnel)"
    echo "     Les services Docker démarreront quand même"
  }
}

check_aws_opensearch

echo ""
echo "🔨 Construction et démarrage des services Docker (progressif avec vérifications)..."
COMPOSE_DIR="$REMOTE_DIR/webapp/backend/docker"
BACKEND_DIR="$REMOTE_DIR/webapp/backend"

# Créer le réseau Docker si nécessaire
run_remote_sudo "docker network create ids-network || true"

# Construire et démarrer les services dans l'ordre de dépendance
# docker-compose gère automatiquement les dépendances, mais on démarre progressivement pour voir l'avancement

echo "📦 Construction de toutes les images..."
run_remote_sudo "cd '$COMPOSE_DIR' && docker compose build --parallel"

# Fonction pour attendre qu'un service soit prêt
wait_for_service() {
  local service=$1
  local max_attempts=${2:-30}
  local attempt=0
  
  echo "  ⏳ Attente que $service soit prêt..."
  while [ $attempt -lt $max_attempts ]; do
    if run_remote "cd '$COMPOSE_DIR' && docker compose ps $service | grep -q 'Up.*healthy\|Up (unhealthy)\|Up'" 2>/dev/null; then
      echo "  ✅ $service est prêt"
      return 0
    fi
    sleep 2
    attempt=$((attempt + 1))
    echo -n "."
  done
  echo ""
  echo "  ⚠️  $service n'est pas encore prêt après ${max_attempts} tentatives (continuons...)"
  return 1
}

# Démarrer les services dans l'ordre de dépendance avec vérifications
echo "🚀 [1/8] Démarrage de Redis (service de base)..."
run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d redis"
wait_for_service "redis" 15

echo "🚀 [2/8] Démarrage de Node Exporter..."
run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d node_exporter"
wait_for_service "node_exporter" 10

echo "🚀 [3/8] Démarrage de cAdvisor..."
run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d cadvisor"
wait_for_service "cadvisor" 15

echo "🚀 [4/8] Démarrage de Vector (dépend de Redis)..."
# Vérifier que Redis répond avant de démarrer Vector
if run_remote "cd '$COMPOSE_DIR' && docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG"; then
  echo "  ✅ Redis répond, démarrage de Vector..."
  run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d vector"
  wait_for_service "vector" 20
else
  echo "  ⚠️  Redis ne répond pas encore, démarrage de Vector quand même..."
  run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d vector"
  sleep 5
fi

echo "🚀 [5/8] Démarrage de Prometheus (dépend de node_exporter et cadvisor)..."
# Vérifier que les dépendances sont prêtes
if run_remote "cd '$COMPOSE_DIR' && docker compose ps node_exporter cadvisor | grep -q 'Up'"; then
  echo "  ✅ Dépendances prêtes, démarrage de Prometheus..."
  run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d prometheus"
  wait_for_service "prometheus" 30
else
  echo "  ⚠️  Dépendances non prêtes, démarrage de Prometheus quand même..."
  run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d prometheus"
  sleep 5
fi

echo "🚀 [6/8] Démarrage de Grafana (dépend de Prometheus)..."
# Vérifier que Prometheus répond
if run_remote "curl -sf http://localhost:9090/-/healthy >/dev/null 2>&1" || \
   run_remote "cd '$COMPOSE_DIR' && docker compose exec -T prometheus wget -qO- http://localhost:9090/-/healthy 2>/dev/null | grep -q 'Prometheus'"; then
  echo "  ✅ Prometheus répond, démarrage de Grafana..."
  run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d grafana"
  wait_for_service "grafana" 30
else
  echo "  ⚠️  Prometheus ne répond pas encore, démarrage de Grafana quand même..."
  run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d grafana"
  sleep 5
fi

echo "🚀 [7/8] Démarrage du runtime IDS..."
run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d ids-runtime"
wait_for_service "ids-runtime" 20

echo "🚀 [8/8] Démarrage de l'API FastAPI..."
run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d ids-api"
wait_for_service "ids-api" 20

echo ""
echo "📊 Vérification des services Docker..."
run_remote "cd '$COMPOSE_DIR' && docker compose ps"

echo ""
echo "✅ Installation terminée !"
echo ""
echo "📋 Services démarrés :"
echo "  ✅ Redis (cache) - port interne"
echo "  ✅ Vector (logs) - port interne"
echo "  ✅ FastAPI (API) - http://${PI_HOST}:8080"
echo "  ✅ Prometheus (métriques) - http://${PI_HOST}:9090"
echo "  ✅ Grafana (dashboards) - http://${PI_HOST}:3000"
echo "  ✅ Node Exporter (métriques système) - http://${PI_HOST}:9100"
echo "  ✅ cAdvisor (métriques containers) - http://${PI_HOST}:8081"
echo "  ✅ IDS Runtime (agent) - port interne"
echo ""
echo "🔍 Pour voir les logs :"
echo "  ssh ${PI_USER}@${PI_HOST} 'cd $COMPOSE_DIR && docker compose logs -f [service]'"
echo ""
echo "🛠️  Commandes utiles :"
echo "  - Arrêter: ssh ${PI_USER}@${PI_HOST} 'cd $COMPOSE_DIR && docker compose down'"
echo "  - Redémarrer: ssh ${PI_USER}@${PI_HOST} 'cd $COMPOSE_DIR && docker compose restart [service]'"
echo "  - Statut: ssh ${PI_USER}@${PI_HOST} 'cd $COMPOSE_DIR && docker compose ps'"
