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

# ====================== FSM (docs/kl.md) ======================
FSM_STATE="WaitUser"
INIT_SUBSTATE=""
COMPONENT_SUBSTATE=""
DEPLOY_STATE="NotStarted"
DEPLOY_STEP=""

declare -A DOCKER_STATE
DOCKER_SERVICES=(redis node_exporter cadvisor vector prometheus grafana ids-runtime ids-api)

fsm_log() {
  echo "🧭 [FSM] $*"
}

fsm_transition() {
  local next="$1"
  local allowed=""
  case "$FSM_STATE" in
    WaitUser) allowed="StartCommand Stopped" ;;
    StartCommand) allowed="Initializing" ;;
    Initializing) allowed="ComponentsStarting Stopped" ;;
    ComponentsStarting) allowed="SupervisorRunning Stopped" ;;
    SupervisorRunning) allowed="Stopping" ;;
    Stopping) allowed="Stopped" ;;
    Stopped) allowed="" ;;
  esac
  if [[ " $allowed " != *" $next "* ]]; then
    echo "❌ Transition FSM invalide: $FSM_STATE -> $next" >&2
    exit 1
  fi
  fsm_log "$FSM_STATE -> $next"
  FSM_STATE="$next"
}

fsm_init_substate() {
  INIT_SUBSTATE="$1"
  fsm_log "Initializing::$INIT_SUBSTATE"
}

fsm_component_substate() {
  COMPONENT_SUBSTATE="$1"
  fsm_log "ComponentsStarting::$COMPONENT_SUBSTATE"
}

fsm_supervisor_substate() {
  fsm_log "SupervisorRunning::$1"
}

fsm_stopping_substate() {
  fsm_log "Stopping::$1"
}

deploy_transition() {
  local next="$1"
  local allowed=""
  case "$DEPLOY_STATE" in
    NotStarted) allowed="CheckingPrereq" ;;
    CheckingPrereq) allowed="PrereqOK PrereqFailed" ;;
    PrereqOK) allowed="InstallingDeps" ;;
    InstallingDeps) allowed="DepsInstalled DepsFailed" ;;
    DepsInstalled) allowed="BuildingDockerImages" ;;
    BuildingDockerImages) allowed="ImagesBuilt BuildFailed" ;;
    ImagesBuilt) allowed="StartingServices" ;;
    StartingServices) allowed="ServicesStarted ServicesFailed" ;;
    ServicesStarted) allowed="VerifyingHealth" ;;
    VerifyingHealth) allowed="HealthOK HealthFailed" ;;
    HealthFailed) allowed="Retrying" ;;
    Retrying) allowed="StartingServices" ;;
    HealthOK) allowed="Deployed" ;;
  esac
  if [[ " $allowed " != *" $next "* ]]; then
    echo "❌ Transition Deployment invalide: $DEPLOY_STATE -> $next" >&2
    exit 1
  fi
  fsm_log "Deployment::$DEPLOY_STATE -> $next"
  DEPLOY_STATE="$next"
}

deploy_step() {
  DEPLOY_STEP="$1"
  fsm_log "DeploymentStep::$DEPLOY_STEP"
}

docker_state_init() {
  for svc in "${DOCKER_SERVICES[@]}"; do
    DOCKER_STATE["$svc"]="DSNotCreated"
  done
}

docker_transition() {
  local svc="$1"
  local next="$2"
  local current="${DOCKER_STATE[$svc]:-DSNotCreated}"
  local allowed=""
  case "$current" in
    DSNotCreated) allowed="DSCreating" ;;
    DSCreating) allowed="DSCreated DSCreateFail" ;;
    DSCreated) allowed="DSStarting" ;;
    DSStarting) allowed="DSRunning DSStartFail" ;;
    DSRunning) allowed="DSHealthy DSUnhealthy DSStopping" ;;
    DSHealthy) allowed="DSRunning" ;;
    DSUnhealthy) allowed="DSRestarting DSStopping" ;;
    DSRestarting) allowed="DSStarting DSRestartFail" ;;
    DSStopping) allowed="DSStopped" ;;
    DSStopped) allowed="DSRemoving" ;;
  esac
  if [[ " $allowed " != *" $next "* ]]; then
    echo "❌ Transition Docker invalide: $svc $current -> $next" >&2
    exit 1
  fi
  fsm_log "Docker::$svc $current -> $next"
  DOCKER_STATE["$svc"]="$next"
}

die() {
  local msg="$1"
  echo "❌ $msg"
  fsm_stop
  exit 1
}

deploy_fail() {
  local state="$1"
  local msg="$2"
  if [ "${DEPLOY_STATE:-}" != "$state" ]; then
    deploy_transition "$state" || true
  fi
  die "$msg"
}

on_error() {
  local code=$?
  case "${DEPLOY_STATE:-}" in
    CheckingPrereq) deploy_transition "PrereqFailed" || true ;;
    InstallingDeps) deploy_transition "DepsFailed" || true ;;
    BuildingDockerImages) deploy_transition "BuildFailed" || true ;;
    StartingServices) deploy_transition "ServicesFailed" || true ;;
    VerifyingHealth) deploy_transition "HealthFailed" || true ;;
  esac
  fsm_stop
  echo "❌ Erreur inattendue (code $code)."
  exit "$code"
}
# ====================== FSM STOP ======================
fsm_stop() {
  case "$FSM_STATE" in
    SupervisorRunning)
      fsm_transition "Stopping" || true
      fsm_stopping_substate "StopSuricata"
      fsm_stopping_substate "StopDocker"
      fsm_stopping_substate "StopResourceController"
      fsm_stopping_substate "AllStopped"
      ;;
    StartCommand)
      fsm_transition "Initializing" || true
      ;;
    Initializing|ComponentsStarting|WaitUser)
      ;;
  esac
  if [ "$FSM_STATE" != "Stopped" ]; then
    fsm_transition "Stopped" || true
  fi
}


trap 'on_error' ERR

require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    die "La commande '$cmd' est requise. Installez-la puis relancez."
  fi
}

# ====================== USER INPUT (WAIT_USER) ======================
fsm_log "WaitUser: en attente d'action utilisateur"
PI_HOST="$(prompt 'IP du Raspberry Pi')"
PI_USER="$(prompt 'Utilisateur SSH' 'pi')"
read -r -s -p "Mot de passe SSH: " PI_PASS
echo ""
read -r -s -p "Mot de passe sudo: " SUDO_PASS
echo ""
REMOTE_DIR="$(prompt 'Répertoire d’installation sur le Pi' '/opt/ids-dashboard')"
MIRROR_INTERFACE="$(prompt 'Interface miroir' 'eth0')"

if [ -z "$PI_HOST" ]; then
  die "IP du Raspberry Pi requise."
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

# ====================== MAIN FSM ======================
fsm_transition "StartCommand"
fsm_transition "Initializing"

fsm_init_substate "LoadingConfig"
CONFIG_PATH="webapp/backend/config.yaml"
if [ ! -f "$CONFIG_PATH" ]; then
  fsm_init_substate "ConfigError"
  die "Config introuvable: $CONFIG_PATH"
fi

fsm_init_substate "ValidatingConfig"
for cmd in sshpass tar ssh scp; do
  require_command "$cmd"
done
if [ -z "$PI_HOST" ] || [ -z "$PI_USER" ]; then
  fsm_init_substate "ConfigError"
  die "PI_HOST ou PI_USER manquant."
fi
fsm_init_substate "ConfigValid"

fsm_transition "ComponentsStarting"
fsm_component_substate "StartResourceController"
echo "🔌 Vérification de la connectivité SSH..."
if ! run_remote "echo 'ok'" >/dev/null 2>&1; then
  die "Impossible de se connecter au Raspberry Pi (SSH)."
fi

fsm_component_substate "StartDockerManager"
echo "🔐 Vérification de sudo sur le Pi..."
if ! run_remote_sudo "echo 'sudo ok'" >/dev/null 2>&1; then
  die "Impossible d'utiliser sudo sur le Pi."
fi

fsm_component_substate "StartSuricataManager"
echo "🧩 Préparation du dossier d'installation distant..."
run_remote_sudo "mkdir -p '$REMOTE_DIR' && chown -R '${PI_USER}:${PI_USER}' '$REMOTE_DIR'"

fsm_component_substate "AllComponentsStarted"

fsm_transition "SupervisorRunning"
fsm_supervisor_substate "SupervisorMonitoring"

# ====================== DEPLOYMENT FSM ======================
deploy_transition "CheckingPrereq"
echo "✅ Prérequis locaux vérifiés."

deploy_transition "PrereqOK"
deploy_transition "InstallingDeps"
deploy_step "DeployToPi"

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

echo "🚚 Transfert du dépôt vers le Pi..."
if ! sshpass -e scp -o StrictHostKeyChecking=accept-new "$ARCHIVE_PATH" \
  "${PI_USER}@${PI_HOST}:/tmp/ids-dashboard.tar.gz"; then
  deploy_fail "DepsFailed" "Échec du transfert vers le Pi."
fi

echo "📂 Extraction sur le Pi..."
if ! run_remote_sudo "rm -rf '$REMOTE_DIR'/*"; then
  deploy_fail "DepsFailed" "Impossible de nettoyer le répertoire distant."
fi
if ! run_remote_sudo "tar -xzf /tmp/ids-dashboard.tar.gz -C '$REMOTE_DIR'"; then
  deploy_fail "DepsFailed" "Échec de l'extraction sur le Pi."
fi
if ! run_remote_sudo "chmod +x '$REMOTE_DIR/depancecmd/'*.sh"; then
  deploy_fail "DepsFailed" "Échec chmod sur les scripts."
fi

deploy_step "InstallDependencies"
echo "🧩 Exécution des scripts d'installation..."
for script in depancecmd/*.sh; do
  script_name="$(basename "$script")"
  echo "➡️  $script_name"
  if ! run_remote_sudo \
    "REMOTE_DIR='$REMOTE_DIR' INSTALL_USER='$PI_USER' MIRROR_INTERFACE='$MIRROR_INTERFACE' bash '$REMOTE_DIR/depancecmd/$script_name'"; then
    echo "❌ Échec sur $script_name."
    echo "➡️  Conseil: éditez $REMOTE_DIR/depancecmd/$script_name pour ajuster la commande."
    echo "➡️  Exemple: ajoutez un paquet manquant via 'apt-get install -y <package>'."
    deploy_fail "DepsFailed" "Installation interrompue sur $script_name."
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
  run_remote_sudo "systemctl start docker || true"
fi

# Vérifier docker compose
if ! run_remote "docker compose version" >/dev/null 2>&1; then
  echo "⚠️  docker compose non disponible, installation..."
  run_remote_sudo "apt-get update && apt-get install -y docker-compose-plugin || apt-get install -y docker-compose"
fi

deploy_transition "DepsInstalled"
deploy_transition "BuildingDockerImages"

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

# ====================== DOCKER SERVICE FSM ======================
docker_state_init

# Créer le réseau Docker si nécessaire
run_remote_sudo "docker network create ids-network || true"

echo "📦 Construction de toutes les images..."
for svc in "${DOCKER_SERVICES[@]}"; do
  docker_transition "$svc" "DSCreating"
done
if ! run_remote_sudo "cd '$COMPOSE_DIR' && docker compose build --parallel"; then
  for svc in "${DOCKER_SERVICES[@]}"; do
    docker_transition "$svc" "DSCreateFail"
  done
  deploy_fail "BuildFailed" "Échec du build Docker."
fi
for svc in "${DOCKER_SERVICES[@]}"; do
  docker_transition "$svc" "DSCreated"
done

deploy_transition "ImagesBuilt"
deploy_transition "StartingServices"

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
docker_transition "redis" "DSStarting"
run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d redis"
docker_transition "redis" "DSRunning"
if wait_for_service "redis" 15; then
  docker_transition "redis" "DSHealthy"
else
  docker_transition "redis" "DSUnhealthy"
fi

echo "🚀 [2/8] Démarrage de Node Exporter..."
docker_transition "node_exporter" "DSStarting"
run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d node_exporter"
docker_transition "node_exporter" "DSRunning"
if wait_for_service "node_exporter" 10; then
  docker_transition "node_exporter" "DSHealthy"
else
  docker_transition "node_exporter" "DSUnhealthy"
fi

echo "🚀 [3/8] Démarrage de cAdvisor..."
docker_transition "cadvisor" "DSStarting"
run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d cadvisor"
docker_transition "cadvisor" "DSRunning"
if wait_for_service "cadvisor" 15; then
  docker_transition "cadvisor" "DSHealthy"
else
  docker_transition "cadvisor" "DSUnhealthy"
fi

echo "🚀 [4/8] Démarrage de Vector (dépend de Redis)..."
# Vérifier que Redis répond avant de démarrer Vector
if run_remote "cd '$COMPOSE_DIR' && docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG"; then
  echo "  ✅ Redis répond, démarrage de Vector..."
  docker_transition "vector" "DSStarting"
  run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d vector"
  docker_transition "vector" "DSRunning"
  if wait_for_service "vector" 20; then
    docker_transition "vector" "DSHealthy"
  else
    docker_transition "vector" "DSUnhealthy"
  fi
else
  echo "  ⚠️  Redis ne répond pas encore, démarrage de Vector quand même..."
  docker_transition "vector" "DSStarting"
  run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d vector"
  docker_transition "vector" "DSRunning"
  sleep 5
  docker_transition "vector" "DSUnhealthy"
fi

echo "🚀 [5/8] Démarrage de Prometheus (dépend de node_exporter et cadvisor)..."
# Vérifier que les dépendances sont prêtes
if run_remote "cd '$COMPOSE_DIR' && docker compose ps node_exporter cadvisor | grep -q 'Up'"; then
  echo "  ✅ Dépendances prêtes, démarrage de Prometheus..."
  docker_transition "prometheus" "DSStarting"
  run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d prometheus"
  docker_transition "prometheus" "DSRunning"
  if wait_for_service "prometheus" 30; then
    docker_transition "prometheus" "DSHealthy"
  else
    docker_transition "prometheus" "DSUnhealthy"
  fi
else
  echo "  ⚠️  Dépendances non prêtes, démarrage de Prometheus quand même..."
  docker_transition "prometheus" "DSStarting"
  run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d prometheus"
  docker_transition "prometheus" "DSRunning"
  sleep 5
  docker_transition "prometheus" "DSUnhealthy"
fi

echo "🚀 [6/8] Démarrage de Grafana (dépend de Prometheus)..."
# Vérifier que Prometheus répond
if run_remote "curl -sf http://localhost:9090/-/healthy >/dev/null 2>&1" || \
   run_remote "cd '$COMPOSE_DIR' && docker compose exec -T prometheus wget -qO- http://localhost:9090/-/healthy 2>/dev/null | grep -q 'Prometheus'"; then
  echo "  ✅ Prometheus répond, démarrage de Grafana..."
  docker_transition "grafana" "DSStarting"
  run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d grafana"
  docker_transition "grafana" "DSRunning"
  if wait_for_service "grafana" 30; then
    docker_transition "grafana" "DSHealthy"
  else
    docker_transition "grafana" "DSUnhealthy"
  fi
else
  echo "  ⚠️  Prometheus ne répond pas encore, démarrage de Grafana quand même..."
  docker_transition "grafana" "DSStarting"
  run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d grafana"
  docker_transition "grafana" "DSRunning"
  sleep 5
  docker_transition "grafana" "DSUnhealthy"
fi

echo "🚀 [7/8] Démarrage du runtime IDS..."
docker_transition "ids-runtime" "DSStarting"
run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d ids-runtime"
docker_transition "ids-runtime" "DSRunning"
if wait_for_service "ids-runtime" 20; then
  docker_transition "ids-runtime" "DSHealthy"
else
  docker_transition "ids-runtime" "DSUnhealthy"
fi

echo "🚀 [8/8] Démarrage de l'API FastAPI..."
docker_transition "ids-api" "DSStarting"
run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d ids-api"
docker_transition "ids-api" "DSRunning"
if wait_for_service "ids-api" 20; then
  docker_transition "ids-api" "DSHealthy"
else
  docker_transition "ids-api" "DSUnhealthy"
fi

deploy_transition "ServicesStarted"
deploy_transition "VerifyingHealth"

fsm_supervisor_substate "SupervisorMonitoring"

health_check() {
  local api_url="http://localhost:8080/api/health"
  run_remote "python3 - << 'PYEOF'
import sys
from urllib.request import urlopen
try:
    with urlopen('$api_url', timeout=5) as resp:
        if resp.status == 200:
            sys.exit(0)
except Exception:
    sys.exit(1)
sys.exit(1)
PYEOF"
}

MAX_HEALTH_RETRIES=2
attempt=0
while [ $attempt -le $MAX_HEALTH_RETRIES ]; do
  if health_check; then
    fsm_supervisor_substate "HealthOK"
    deploy_transition "HealthOK"
    deploy_transition "Deployed"
    fsm_supervisor_substate "SupervisorMonitoring"
    break
  fi
  if [ $attempt -eq $MAX_HEALTH_RETRIES ]; then
    fsm_supervisor_substate "SupervisorDegraded"
    deploy_transition "HealthFailed"
    deploy_fail "HealthFailed" "Health check FastAPI échoué."
  fi
  fsm_supervisor_substate "SupervisorDegraded"
  deploy_transition "HealthFailed"
  fsm_supervisor_substate "SupervisorRecovering"
  deploy_transition "Retrying"
  deploy_transition "StartingServices"
  attempt=$((attempt + 1))
  echo "🔁 Tentative de redémarrage des services (essai ${attempt}/${MAX_HEALTH_RETRIES})..."
  run_remote_sudo "cd '$COMPOSE_DIR' && docker compose restart ids-api ids-runtime"
  deploy_transition "ServicesStarted"
  deploy_transition "VerifyingHealth"
done

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
