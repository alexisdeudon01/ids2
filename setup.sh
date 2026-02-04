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

# Check for required commands
MISSING_CMDS=()
for cmd in sshpass tar ssh scp; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    MISSING_CMDS+=("$cmd")
  fi
done

if [ ${#MISSING_CMDS[@]} -gt 0 ]; then
  echo "❌ Missing required commands: ${MISSING_CMDS[*]}"
  echo "Install with: sudo apt-get install -y sshpass openssh-client tar"
  exit 1
fi

PI_HOST="$(prompt 'IP du Raspberry Pi')"
PI_USER="$(prompt 'Utilisateur SSH' 'pi')"
read -r -s -p "Mot de passe SSH: " PI_PASS
echo ""
read -r -s -p "Mot de passe sudo: " SUDO_PASS
echo ""

# Security: Clear passwords from environment after use
# Note: Passwords are still visible in process list during script execution
# For better security, consider using SSH keys instead of passwords
cleanup_passwords() {
  PI_PASS=""
  SUDO_PASS=""
  export PI_PASS=""
  export SUDO_PASS=""
}
trap cleanup_passwords EXIT

REMOTE_DIR="$(prompt 'Répertoire d’installation sur le Pi' '/opt/ids-dashboard')"
MIRROR_INTERFACE="$(prompt 'Interface miroir' 'eth0')"

if [ -z "$PI_HOST" ]; then
  echo "IP du Raspberry Pi requise."
  exit 1
fi

run_remote() {
  local cmd="$1"
  if ! sshpass -p "$PI_PASS" ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 \
      "${PI_USER}@${PI_HOST}" "$cmd"; then
    echo "❌ Échec de la commande SSH: $cmd"
    return 1
  fi
}

run_remote_sudo() {
  local cmd="$1"
  if ! sshpass -p "$PI_PASS" ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 \
      "${PI_USER}@${PI_HOST}" \
      "echo '$SUDO_PASS' | sudo -S -p '' bash -lc $(printf %q "$cmd")"; then
    echo "❌ Échec de la commande sudo SSH: $cmd"
    return 1
  fi
}

echo "📦 Préparation du paquet..."
ARCHIVE_PATH="$(mktemp -t ids-dashboard-XXXXXX.tar.gz)"
# Set restrictive permissions to prevent other users from accessing the archive
chmod 600 "$ARCHIVE_PATH"
tar \
  --exclude=webapp/frontend/node_modules \
  --exclude=webapp/backend/.venv \
  --exclude=webapp/backend/venv \
  --exclude=__pycache__ \
  -czf "$ARCHIVE_PATH" .
# Cleanup function to remove archive on exit
cleanup() {
  [ -f "$ARCHIVE_PATH" ] && rm -f "$ARCHIVE_PATH"
}
trap cleanup EXIT INT TERM

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
# Verify depancecmd directory exists before proceeding
if [ ! -d "depancecmd" ] || [ -z "$(ls -A depancecmd/*.sh 2>/dev/null)" ]; then
  echo "❌ Erreur: Le répertoire depancecmd ou ses scripts .sh sont introuvables."
  exit 1
fi

# Validate environment variables before passing to remote scripts
if [ -z "$REMOTE_DIR" ]; then
  echo "❌ REMOTE_DIR is not set"
  exit 1
fi
if [ -z "$PI_USER" ]; then
  echo "❌ INSTALL_USER (PI_USER) is not set"
  exit 1
fi
if [ -z "$MIRROR_INTERFACE" ]; then
  echo "⚠️  Warning: MIRROR_INTERFACE is not set, using default 'eth0'"
  MIRROR_INTERFACE="eth0"
fi

FAILED_SCRIPTS=()
for script in depancecmd/*.sh; do
  script_name="$(basename "$script")"
  echo "➡️  $script_name"
  if ! run_remote_sudo \
    "REMOTE_DIR='$REMOTE_DIR' INSTALL_USER='$PI_USER' MIRROR_INTERFACE='$MIRROR_INTERFACE' bash '$REMOTE_DIR/depancecmd/$script_name'"; then
    echo "❌ Échec sur $script_name."
    FAILED_SCRIPTS+=("$script_name")
    echo "➡️  Conseil: éditez $REMOTE_DIR/depancecmd/$script_name pour ajuster la commande."
    echo "➡️  Exemple: ajoutez un paquet manquant via 'apt-get install -y <package>'."
  else
    echo "✅ $script_name terminé."
  fi
done

if [ ${#FAILED_SCRIPTS[@]} -gt 0 ]; then
  echo "⚠️  Warning: ${#FAILED_SCRIPTS[@]} script(s) failed: ${FAILED_SCRIPTS[*]}"
  echo "   Installation may be incomplete. Review errors above."
  exit_code=1
else
  exit_code=0
fi

# Clear passwords before exit
cleanup_passwords

echo "✅ Installation terminée. Vérifiez les services et l'interface web."
exit $exit_code