#!/usr/bin/env bash
set -euo pipefail

REMOTE_DIR="${REMOTE_DIR:-/opt/ids-dashboard}"

# Validate REMOTE_DIR is not empty
if [ -z "$REMOTE_DIR" ]; then
  echo "❌ REMOTE_DIR is not set or empty"
  exit 1
fi

REQ_FILE="${REMOTE_DIR}/webapp/backend/requirements.txt"
VENV_DIR="${REMOTE_DIR}/webapp/backend/venv"

if [ ! -f "$REQ_FILE" ]; then
  echo "❌ requirements.txt introuvable: $REQ_FILE"
  exit 1
fi

# Check python3 availability
if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ python3 command not found. Please install Python 3 first."
  exit 1
fi

# Check python3-venv module
if ! python3 -c "import venv" 2>/dev/null; then
  echo "❌ python3-venv module not available. Installing python3-venv..."
  if [ "$EUID" -eq 0 ] || sudo -n true 2>/dev/null; then
    apt-get update && apt-get install -y python3-venv
  else
    echo "❌ Cannot install python3-venv without root privileges."
    exit 1
  fi
fi

# Create venv if not exists
if [ ! -d "$VENV_DIR" ]; then
  echo "📦 Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
fi

# Install dependencies in venv
echo "📥 Installing Python dependencies..."

# Check network connectivity before pip install
if ! ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1 && ! ping -c 1 -W 2 1.1.1.1 >/dev/null 2>&1; then
    echo "⚠️  Warning: Network connectivity check failed. pip install may fail."
fi

# Upgrade pip with retry
max_retries=3
retry_count=0
while [ $retry_count -lt $max_retries ]; do
    if "$VENV_DIR/bin/pip" install --upgrade pip --timeout=60; then
        break
    else
        retry_count=$((retry_count + 1))
        if [ $retry_count -lt $max_retries ]; then
            echo "⚠️  pip upgrade failed, retrying ($retry_count/$max_retries)..."
            sleep 3
        else
            echo "❌ Failed to upgrade pip after $max_retries attempts"
            exit 1
        fi
    fi
done

# Install requirements with retry
retry_count=0
while [ $retry_count -lt $max_retries ]; do
    if "$VENV_DIR/bin/pip" install -r "$REQ_FILE" --timeout=300; then
        echo "✅ Backend dependencies installed in venv"
        exit 0
    else
        retry_count=$((retry_count + 1))
        if [ $retry_count -lt $max_retries ]; then
            echo "⚠️  pip install failed, retrying ($retry_count/$max_retries)..."
            sleep 5
        else
            echo "❌ Failed to install dependencies after $max_retries attempts"
            echo "   Some packages may have failed. Check the output above for details."
            exit 1
        fi
    fi
done

