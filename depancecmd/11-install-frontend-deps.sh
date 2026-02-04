#!/usr/bin/env bash
set -euo pipefail

REMOTE_DIR="${REMOTE_DIR:-/opt/ids-dashboard}"
INSTALL_USER="${INSTALL_USER:-${SUDO_USER:-$USER}}"

# Validate REMOTE_DIR is not empty
if [ -z "$REMOTE_DIR" ]; then
  echo "❌ REMOTE_DIR is not set"
  exit 1
fi

# Try multiple possible frontend directory locations
FRONT_DIR=""
for possible_dir in "${REMOTE_DIR}/webapp/frontend" "${REMOTE_DIR}/frontend" "webapp/frontend" "frontend"; do
  if [ -f "${possible_dir}/package.json" ]; then
    FRONT_DIR="$possible_dir"
    break
  fi
done

if [ -z "$FRONT_DIR" ] || [ ! -f "$FRONT_DIR/package.json" ]; then
  echo "⚠️  package.json introuvable dans les emplacements standards"
  echo "   Cherché dans: ${REMOTE_DIR}/webapp/frontend, ${REMOTE_DIR}/frontend, webapp/frontend, frontend"
  exit 0
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "❌ npm non disponible. Installez-le via depancecmd/04-install-node.sh."
  exit 1
fi

# Use npm install with --mutex flag to prevent conflicts
sudo -u "$INSTALL_USER" bash -c "cd '$FRONT_DIR' && npm install --mutex=file:/tmp/npm-install.lock"
