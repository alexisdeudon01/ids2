#!/usr/bin/env bash
set -euo pipefail

REMOTE_DIR="${REMOTE_DIR:-/opt/ids-dashboard}"
INSTALL_USER="${INSTALL_USER:-${SUDO_USER:-$USER}}"
FRONT_DIR="${REMOTE_DIR}/webapp/frontend"

if [ ! -f "$FRONT_DIR/package.json" ]; then
  echo "package.json introuvable: $FRONT_DIR"
  exit 0
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm non disponible. Installez-le via depancecmd/04-install-node.sh."
  exit 1
fi

sudo -u "$INSTALL_USER" bash -c "cd '$FRONT_DIR' && npm install"
