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
echo "🔨 Construction et démarrage des services Docker (progressif)..."
COMPOSE_DIR="$REMOTE_DIR/webapp/backend/docker"
BACKEND_DIR="$REMOTE_DIR/webapp/backend"

# Créer le réseau Docker si nécessaire
run_remote_sudo "docker network create ids-network || true"

# Construire et démarrer les services dans l'ordre de dépendance
# docker-compose gère automatiquement les dépendances, mais on démarre progressivement pour voir l'avancement

echo "📦 Construction de toutes les images..."
run_remote_sudo "cd '$COMPOSE_DIR' && docker compose build --parallel"

# Démarrer les services dans l'ordre de dépendance
echo "🚀 [1/8] Démarrage de Redis (service de base)..."
run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d redis"
sleep 2

echo "🚀 [2/8] Démarrage de Node Exporter..."
run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d node_exporter"
sleep 1

echo "🚀 [3/8] Démarrage de cAdvisor..."
run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d cadvisor"
sleep 2

echo "🚀 [4/8] Démarrage de Vector (dépend de Redis)..."
run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d vector"
sleep 2

echo "🚀 [5/8] Démarrage de Prometheus (dépend de node_exporter et cadvisor)..."
run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d prometheus"
sleep 2

echo "🚀 [6/8] Démarrage de Grafana (dépend de Prometheus)..."
run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d grafana"
sleep 2

echo "🚀 [7/8] Démarrage du runtime IDS..."
run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d ids-runtime"
sleep 2

echo "🚀 [8/8] Démarrage de l'API FastAPI..."
run_remote_sudo "cd '$COMPOSE_DIR' && docker compose up -d ids-api"
sleep 2

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
