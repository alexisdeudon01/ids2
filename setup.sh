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

if ! command -v sshpass >/dev/null 2>&1; then
  echo "sshpass is required. Install with: sudo apt-get install -y sshpass"
  exit 1
fi

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

run_remote() {
  local cmd="$1"
  sshpass -p "$PI_PASS" ssh -o StrictHostKeyChecking=accept-new "${PI_USER}@${PI_HOST}" "$cmd"
}

run_remote_sudo() {
  local cmd="$1"
  sshpass -p "$PI_PASS" ssh -o StrictHostKeyChecking=accept-new "${PI_USER}@${PI_HOST}" \
    "echo '$SUDO_PASS' | sudo -S -p '' bash -lc $(printf %q "$cmd")"
}

echo "📦 Préparation du paquet..."
ARCHIVE_PATH="$(mktemp -t ids-dashboard-XXXXXX.tar.gz)"
tar \
  --exclude=.git \
  --exclude=webapp/frontend/node_modules \
  --exclude=webapp/backend/.venv \
  --exclude=webapp/backend/venv \
  --exclude=__pycache__ \
  -czf "$ARCHIVE_PATH" .

echo "🔐 Création du répertoire distant..."
run_remote_sudo "mkdir -p '$REMOTE_DIR' && chown -R '${PI_USER}:${PI_USER}' '$REMOTE_DIR'"

echo "🚚 Transfert du dépôt vers le Pi..."
sshpass -p "$PI_PASS" scp -o StrictHostKeyChecking=accept-new "$ARCHIVE_PATH" \
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

echo "✅ Installation terminée. Vérifiez les services et l'interface web."
