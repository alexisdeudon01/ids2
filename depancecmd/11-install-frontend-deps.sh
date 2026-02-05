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

# Check network connectivity before npm install
if ! ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1 && ! ping -c 1 -W 2 1.1.1.1 >/dev/null 2>&1; then
    echo "⚠️  Warning: Network connectivity check failed. npm install may fail."
fi

# Use npm install with --mutex flag to prevent conflicts
# Retry mechanism for network failures
max_retries=3
retry_count=0
while [ $retry_count -lt $max_retries ]; do
    if sudo -u "$INSTALL_USER" bash -c "cd '$FRONT_DIR' && npm install --mutex=file:/tmp/npm-install.lock --timeout=300000"; then
        echo "✅ Frontend dependencies installed"
        exit 0
    else
        retry_count=$((retry_count + 1))
        if [ $retry_count -lt $max_retries ]; then
            echo "⚠️  npm install failed, retrying ($retry_count/$max_retries)..."
            sleep 5
        else
            echo "❌ Failed to install frontend dependencies after $max_retries attempts"
            exit 1
        fi
    fi
done
